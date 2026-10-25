package com.larkspur.route;

import java.time.Instant;
import java.util.List;

public record RouteResult(List<Leg> legs, ErrorCode error) {

    public record Leg(String from, String to, long priceCents, Instant eta) {}

    public static RouteResult complete(List<Leg> legs) {
        return new RouteResult(List.copyOf(legs), null);
    }

    public static RouteResult partial(List<Leg> legs, ErrorCode error) {
        return new RouteResult(List.copyOf(legs), error);
    }

    public boolean isComplete() {
        return error == null;
    }
}
