package com.larkspur.route;

import java.time.Instant;
import java.util.List;

public record RouteRequest(String carrierId, List<String> stops, Instant departure, int stopMinutes) {
    public RouteRequest {
        if (stops == null || stops.size() < 2) {
            throw new IllegalArgumentException("a route needs at least two stops");
        }
        stops = List.copyOf(stops);
    }
}
