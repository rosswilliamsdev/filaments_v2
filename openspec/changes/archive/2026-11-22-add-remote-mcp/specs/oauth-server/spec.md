## ADDED Requirements

### Requirement: Lockout counts the visitor's real address behind the tunnel
When a request carries a `CF-Connecting-IP` header holding a valid IP address, the login lockout SHALL count attempts against that address instead of the proxy's address; an invalid value SHALL be ignored. Requests without the header SHALL use the connection address as before.

#### Scenario: Two visitors through the tunnel
- **WHEN** one address fails to sign in 10 times through the tunnel
- **THEN** that address is locked out and a different visitor's address can still sign in

#### Scenario: Local request
- **WHEN** a request arrives directly on `127.0.0.1` without the header
- **THEN** the lockout uses `127.0.0.1`
