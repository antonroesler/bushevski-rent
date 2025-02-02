# Backend Requirements for Bushevski Camper Rental

## Database Schema

### Tables

#### 1. Bookings

- `id` (UUID, Primary Key)
- `startDate` (Date)
- `endDate` (Date)
- `pickupTime` (Time)
- `returnTime` (Time)
- `status` (Enum: 'pending', 'confirmed', 'completed', 'cancelled')
- `totalPrice` (Decimal)
- `nightlyRates` (Decimal)
- `serviceFee` (Decimal)
- `earlyPickupFee` (Decimal, nullable)
- `lateReturnFee` (Decimal, nullable)
- `parkingFee` (Decimal, nullable)
- `deliveryFee` (Decimal, nullable)
- `createdAt` (Timestamp)
- `updatedAt` (Timestamp)

#### 2. Customers

- `id` (UUID, Primary Key)
- `firstName` (String)
- `lastName` (String)
- `email` (String, unique)
- `phone` (String)
- `street` (String)
- `city` (String)
- `postalCode` (String)
- `country` (String)
- `driversLicenseUrl` (String, nullable)
- `createdAt` (Timestamp)
- `updatedAt` (Timestamp)

#### 3. BookingCustomer (Junction table for future extensibility)

- `bookingId` (UUID, Foreign Key)
- `customerId` (UUID, Foreign Key)
- Primary Key: (bookingId, customerId)

#### 4. PricingRules

- `id` (UUID, Primary Key)
- `startDate` (Date)
- `endDate` (Date)
- `basePrice` (Decimal)
- `minStay` (Integer)
- `createdAt` (Timestamp)
- `updatedAt` (Timestamp)

#### 5. BlockedDates

- `id` (UUID, Primary Key)
- `startDate` (Date)
- `endDate` (Date)
- `reason` (String: 'maintenance', 'private', 'other')
- `notes` (String, nullable)
- `createdAt` (Timestamp)
- `updatedAt` (Timestamp)

## API Routes

### Customer-Facing API

#### Availability & Pricing

```
GET /api/availability
- Query params: startDate, endDate
- Returns: Available dates and pricing for the period
```

```
GET /api/pricing
- Query params: startDate, endDate
- Returns: Detailed pricing information including base rates and fees
```

#### Bookings

```
POST /api/bookings
- Body: All booking details including customer info
- Returns: Booking confirmation with ID
```

```
GET /api/bookings/{bookingId}
- Returns: Public booking details
```

```
PUT /api/bookings/{bookingId}/drivers-license
- Body: Driver's license file (multipart/form-data)
- Returns: Upload confirmation
```

### Admin API

#### Bookings Management

```
GET /api/admin/bookings
- Query params: startDate, endDate, status
- Returns: All bookings with full details
```

```
PUT /api/admin/bookings/{bookingId}/status
- Body: new status
- Returns: Updated booking
```

```
DELETE /api/admin/bookings/{bookingId}
- Returns: Deletion confirmation
```

#### Pricing Management

```
POST /api/admin/pricing-rules
- Body: startDate, endDate, basePrice, minStay
- Returns: Created pricing rule
```

```
GET /api/admin/pricing-rules
- Query params: startDate, endDate
- Returns: All pricing rules for the period
```

```
PUT /api/admin/pricing-rules/{ruleId}
- Body: Updated rule details
- Returns: Updated rule
```

```
DELETE /api/admin/pricing-rules/{ruleId}
- Returns: Deletion confirmation
```

#### Blocked Dates Management

```
POST /api/admin/blocked-dates
- Body: startDate, endDate, reason, notes
- Returns: Created blocked period
```

```
GET /api/admin/blocked-dates
- Query params: startDate, endDate
- Returns: All blocked periods
```

```
DELETE /api/admin/blocked-dates/{id}
- Returns: Deletion confirmation
```

## Security Requirements

### Authentication

- Admin API routes require API Key authentication
- Admin page will be hosted on local host of the admin, with a local env var for the API key

### Authorization

- Customer-facing routes: No authentication required except for viewing own booking details
- Admin routes: Require admin role in JWT token
- Rate limiting applied to all routes
- CORS configured for frontend domains only

## AWS Services Integration

### Primary Services

- API Gateway: REST API endpoints
- Lambda: Business logic implementation
- DynamoDB: Data storage
- S3: Driver's license file storage
- CloudWatch: Logging and monitoring

### DynamoDB Design

- Use single-table design
- GSIs for efficient queries:
  - BookingsByDate: Query bookings by date range
  - BookingsByStatus: Query bookings by status
  - CustomersByEmail: Look up customers by email

## Additional Requirements

### Validation

- Date ranges must be valid
- No overlapping bookings allowed
- Pricing rules cannot overlap
- All required customer information must be provided
- Phone numbers must be in valid format
- Email addresses must be valid
- Postal codes must be valid for the specified country

### Business Rules

- Minimum stay periods must be enforced
- Early pickup/late return fees must be automatically calculated
- Delivery distance must be within allowed range
- Parking service availability must be confirmed
- Total price must be calculated consistently between frontend and backend

### Error Handling

- Proper error messages for all validation failures
- Booking conflicts must be clearly communicated
- Network errors must be handled gracefully
- Rate limiting must return appropriate status codes
- All errors must be logged for monitoring

### Monitoring

- CloudWatch metrics for:
  - Booking success/failure rates
  - API response times
  - Error rates
  - Lambda execution times
  - DynamoDB capacity usage
