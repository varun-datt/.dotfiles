package com.larkspur.route;

import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public final class RoutePlanner {

    private final CarrierClient carriers;
    private final EtaEstimator eta;
    private final Clock clock;
    private final long planDeadlineMs;

    public RoutePlanner(CarrierClient carriers, EtaEstimator eta, Clock clock, long planDeadlineMs) {
        this.carriers = carriers;
        this.eta = eta;
        this.clock = clock;
        this.planDeadlineMs = planDeadlineMs;
    }

    public RouteResult plan(RouteRequest request) {
        Instant deadline = clock.instant().plusMillis(planDeadlineMs);
        List<RouteResult.Leg> legs = new ArrayList<>();
        Instant departure = request.departure();

        for (int i = 0; i + 1 < request.stops().size(); i++) {
            String from = request.stops().get(i);
            String to = request.stops().get(i + 1);

            if (clock.instant().isAfter(deadline)) {
                return RouteResult.partial(legs, ErrorCode.ERR_ROUTE_TIMEOUT);
            }

            CarrierClient.Quote quote;
            try {
                quote = carriers.quote(request.carrierId(), from, to);
            } catch (CarrierClient.CarrierTimeoutException e) {
                return RouteResult.partial(legs, ErrorCode.ERR_ROUTE_TIMEOUT);
            } catch (CarrierClient.CarrierRejectedException e) {
                return RouteResult.partial(legs, ErrorCode.ERR_CARRIER_REJECTED);
            }

            Instant arrival = eta.estimate(departure, quote.transitMinutes(), quote.distanceKm());
            legs.add(new RouteResult.Leg(from, to, quote.priceCents(), arrival));
            departure = arrival.plusSeconds(request.stopMinutes() * 60L);
        }
        return RouteResult.complete(legs);
    }
}
