package com.larkspur.route;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

public class CarrierClient {

    public record Quote(long priceCents, int transitMinutes, int distanceKm) {}

    public static class CarrierTimeoutException extends Exception {
        public CarrierTimeoutException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    public static class CarrierRejectedException extends Exception {
        public CarrierRejectedException(String message) {
            super(message);
        }
    }

    public static class CarrierHttpException extends Exception {
        private final int statusCode;

        public CarrierHttpException(int statusCode) {
            super("carrier returned HTTP " + statusCode);
            this.statusCode = statusCode;
        }

        public int statusCode() {
            return statusCode;
        }
    }

    private final HttpClient http;
    private final URI baseUrl;
    private final Duration timeout;
    private final RetryPolicy retry;

    public CarrierClient(HttpClient http, URI baseUrl, Duration timeout, RetryPolicy retry) {
        this.http = http;
        this.baseUrl = baseUrl;
        this.timeout = timeout;
        this.retry = retry;
    }

    public Quote quote(String carrierId, String from, String to)
            throws CarrierTimeoutException, CarrierRejectedException {
        try {
            return retry.execute(() -> fetchQuote(carrierId, from, to));
        } catch (CarrierTimeoutException | CarrierRejectedException e) {
            throw e;
        } catch (CarrierHttpException e) {
            throw new CarrierRejectedException(e.getMessage());
        } catch (Exception e) {
            throw new CarrierTimeoutException("carrier " + carrierId + " failed", e);
        }
    }

    private Quote fetchQuote(String carrierId, String from, String to) throws Exception {
        String query = "carrier=" + enc(carrierId) + "&from=" + enc(from) + "&to=" + enc(to);
        HttpRequest request = HttpRequest.newBuilder(baseUrl.resolve("/v2/rates?" + query))
                .timeout(timeout)
                .GET()
                .build();
        HttpResponse<String> response;
        try {
            response = http.send(request, HttpResponse.BodyHandlers.ofString());
        } catch (HttpTimeoutException e) {
            throw new CarrierTimeoutException("carrier " + carrierId + " timed out", e);
        }
        if (response.statusCode() == 422) {
            throw new CarrierRejectedException("lane not served: " + from + " to " + to);
        }
        if (response.statusCode() != 200) {
            throw new CarrierHttpException(response.statusCode());
        }
        return parse(response.body());
    }

    private static String enc(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    static Quote parse(String body) {
        String[] parts = body.trim().split(",");
        return new Quote(Long.parseLong(parts[0]), Integer.parseInt(parts[1]), Integer.parseInt(parts[2]));
    }
}
