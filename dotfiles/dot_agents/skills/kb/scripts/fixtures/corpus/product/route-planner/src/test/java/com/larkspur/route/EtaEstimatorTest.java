package com.larkspur.route;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class EtaEstimatorTest {

    private static final Instant DEPART = Instant.parse("2026-10-01T06:00:00Z");

    @Test
    void shortLegHasNoRestStop() {
        EtaEstimator eta = new EtaEstimator(true);
        assertEquals(DEPART.plusSeconds(120 * 60), eta.estimate(DEPART, 120, 140));
    }

    @Test
    void longLegAddsRestStopsWithModelV2() {
        EtaEstimator eta = new EtaEstimator(true);
        assertEquals(DEPART.plusSeconds((600 + 30) * 60), eta.estimate(DEPART, 600, 820));
    }

    @Test
    void modelV1IgnoresRestStops() {
        EtaEstimator eta = new EtaEstimator(false);
        assertEquals(DEPART.plusSeconds(600 * 60), eta.estimate(DEPART, 600, 820));
    }
}
