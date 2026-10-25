package com.larkspur.route;

import java.util.Random;

/** Exponential backoff with full jitter. See decision 2026-08-14. */
public final class RetryPolicy {

    @FunctionalInterface
    public interface CheckedSupplier<T> {
        T get() throws Exception;
    }

    public interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    private final int maxAttempts;
    private final long baseDelayMs;
    private final long maxDelayMs;
    private final Random random;
    private final Sleeper sleeper;

    public RetryPolicy(int maxAttempts, long baseDelayMs, long maxDelayMs, Random random, Sleeper sleeper) {
        if (maxAttempts < 1) {
            throw new IllegalArgumentException("maxAttempts must be at least 1");
        }
        this.maxAttempts = maxAttempts;
        this.baseDelayMs = baseDelayMs;
        this.maxDelayMs = maxDelayMs;
        this.random = random;
        this.sleeper = sleeper;
    }

    public static RetryPolicy defaults() {
        return new RetryPolicy(3, 200, 2000, new Random(), Thread::sleep);
    }

    public int maxAttempts() {
        return maxAttempts;
    }

    /** Delay before retry number {@code attempt} (1-based): random in [0, min(cap, base * 2^attempt)]. */
    public long delayMs(int attempt) {
        long ceiling = Math.min(maxDelayMs, baseDelayMs << Math.min(attempt, 20));
        return (long) (random.nextDouble() * (ceiling + 1));
    }

    public boolean isRetryable(Exception e) {
        if (e instanceof CarrierClient.CarrierTimeoutException) {
            return true;
        }
        return e instanceof CarrierClient.CarrierHttpException http && http.statusCode() == 503;
    }

    public <T> T execute(CheckedSupplier<T> call) throws Exception {
        Exception last = null;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                return call.get();
            } catch (Exception e) {
                last = e;
                if (!isRetryable(e) || attempt == maxAttempts) {
                    throw e;
                }
                sleeper.sleep(delayMs(attempt));
            }
        }
        throw last;
    }
}
