# Authentication Mechanism

## First Iteration:

### Authenticating from Backend Service

As of now, the UI validates the user credentials and signs them in to the platform. The credentials are hard coded as `username = "admin"` and `password = "admin"` in the UI component (in App.tsx file). Lets keep the same username and password but the authentication should happen from backend. This provides more security to our backend apis in future when we introduce database and persisting user credentials.

### Technical Consideration

- Introduce new end point called "Login" which can receive 2 inputs, username and password.
- Introduce a new service layer in our backend called "Services" which handles business logics.
- Introduce a Login Service in the Services layer to have the business logic for login api.
- The final structure would be Login API (API Layer) -> Login Service (Service Layer).