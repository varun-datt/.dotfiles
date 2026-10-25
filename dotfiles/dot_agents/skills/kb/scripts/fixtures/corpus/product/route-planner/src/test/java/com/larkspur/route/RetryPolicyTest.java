package com.larkspur.route;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import org.junit.jupiter.api.Test;

class RetryPolicyTest {

    private final List<Long> sleeps = new ArrayList<>();

    private RetryPolicy policy(int maxAttempts) {
        return new RetryPolicy(maxAttempts, 200, 2000, new Random(42), sleeps::add);
    }

    @Test
    void delayStaysWithinJitterCeiling() {
        RetryPolicy p = policy(3);
        for (int attempt = 1; attempt <= 6; attempt++) {
            long ceiling = Math.min(2000, 200L << attempt);
            long delay = p.delayMs(attempt);
            assertTrue(delay >= 0 && delay <= ceiling, "attempt " + attempt + " delay " + delay);
        }
    }

    @Test
    void retriesTimeoutsUpToMaxAttempts() {
        RetryPolicy p = policy(3);
        int[] calls = {0};
        assertThrows(CarrierClient.CarrierTimeoutException.class, () -> p.execute(() -> {
            calls[0]++;
            throw new CarrierClient.CarrierTimeoutException("slow", null);
        }));
        assertEquals(3, calls[0]);
        assertEquals(2, sleeps.size());
    }

    @Test
    void doesNotRetryRejections() {
        RetryPolicy p = policy(3);
        int[] calls = {0};
        assertThrows(CarrierClient.CarrierRejectedException.class, () -> p.execute(() -> {
            calls[0]++;
            throw new CarrierClient.CarrierRejectedException("lane not served");
        }));
        assertEquals(1, calls[0]);
    }
}
