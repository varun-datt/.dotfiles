package com.larkspur.route;

import java.time.Instant;

public class EtaEstimator {

    static final int DRIVING_MINUTES_BEFORE_REST = 8 * 60;
    static final int REST_STOP_MINUTES = 30;

    private final boolean modelV2;

    public EtaEstimator(boolean modelV2) {
        this.modelV2 = modelV2;
    }

    /** Arrival time for a leg; with model v2, adds mandatory rest stops on long legs. */
    public Instant estimate(Instant departure, int transitMinutes, int distanceKm) {
        int minutes = transitMinutes;
        if (modelV2) {
            minutes += restStops(transitMinutes) * REST_STOP_MINUTES;
        }
        return departure.plusSeconds(minutes * 60L);
    }

    static int restStops(int transitMinutes) {
        if (transitMinutes <= DRIVING_MINUTES_BEFORE_REST) {
            return 0;
        }
        return (transitMinutes - 1) / DRIVING_MINUTES_BEFORE_REST;
    }
}
