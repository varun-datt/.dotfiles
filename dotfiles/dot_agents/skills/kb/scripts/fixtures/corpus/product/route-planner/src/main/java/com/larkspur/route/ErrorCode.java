package com.larkspur.route;

public enum ErrorCode {
    ERR_ROUTE_TIMEOUT("Plan deadline reached before all legs were priced"),
    ERR_CARRIER_REJECTED("Carrier refused the lane or the request"),
    ERR_NO_ROUTE("No carrier serves one of the legs");

    private final String description;

    ErrorCode(String description) {
        this.description = description;
    }

    public String description() {
        return description;
    }
}
