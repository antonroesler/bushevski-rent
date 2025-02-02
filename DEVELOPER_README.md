# Bushevski Camper Rental - Developer Documentation

## Project Overview

Bushevski is a camper van rental platform built with React and TypeScript, using a serverless AWS backend. The application consists of a customer-facing booking platform and an admin interface for managing bookings, pricing, and availability.

## Technology Stack

### Frontend

- React 18.3
- TypeScript 5.5
- Vite 5.4
- TailwindCSS 3.4
- React Router 6.22
- date-fns for date manipulation
- Lucide React for icons

### Backend (AWS Serverless)

- API Gateway
- Lambda Functions
- DynamoDB
- S3 (file storage)
- CloudFront
- API Key (admin authentication)

## Architecture

### Frontend Deployment

- Frontend assets hosted on S3
- CloudFront distribution for global CDN
- Custom domain with SSL/TLS
- Environment variables managed through AWS Parameter Store

### Backend Integration

- Frontend calls AWS API Gateway endpoints
- CORS configured for frontend domains
- API Gateway integrates with Lambda functions
- Lambda functions interact with DynamoDB
- S3 for storing user-uploaded files (driver's licenses)

## Frontend Architecture

### Key Components

#### Calendar Component

- Handles date selection and availability display
- Integrates with pricing service
- Manages minimum stay requirements
- Prevents invalid date selections

#### Booking Flow

1. Date Selection
2. Personal Information
3. Additional Services
4. Booking Summary

### Price Calculations

All price calculations are performed both frontend and backend for validation:

```typescript
interface PriceCalculation {
  nightlyRates: number; // Sum of nightly rates for selected period
  serviceFee: number; // Fixed €50
  earlyPickupFee: number; // €50 if pickup before 12:00
  lateReturnFee: number; // €50 if return after 16:00
  parkingFee: number; // €5 per night
  deliveryFee: number; // €0.2 per km
}
```

#### Pricing Rules

- Base prices set by admin for date ranges
- Weekend rates 20% higher
- Minimum stay periods:
  - May-Sep: 5 nights
  - Oct-Apr: 3 nights

#### Additional Fees

- Early pickup (before 12:00): +€50
- Late return (after 16:00): +€50
- Parking: €5 per night
- Delivery: €0.2 per km

## Backend Integration

### API Endpoints

Frontend makes calls to these main endpoints:

```typescript
// Get availability and pricing
GET /api/availability?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD

// Create booking
POST /api/bookings
{
  customer: {
    firstName: string;
    lastName: string;
    email: string;
    phone: string;
    address: {
      street: string;
      city: string;
      postalCode: string;
      country: string;
    }
  },
  booking: {
    startDate: string;
    endDate: string;
    pickupTime: string;
    returnTime: string;
    services: {
      parking: boolean;
      deliveryDistance: number;
    }
  }
}

// Upload driver's license
PUT /api/bookings/{bookingId}/drivers-license
Content-Type: multipart/form-data
```

### Error Handling

Frontend handles these error cases:

- Network errors
- Validation errors
- Booking conflicts
- Rate limiting
- Server errors

Error responses follow this structure:

```typescript
interface ErrorResponse {
  code: string;
  message: string;
  details?: Record<string, string>;
}
```

## Development Setup

### Environment Variables

```
VITE_API_URL=https://api.bushevski.com
VITE_ASSETS_URL=https://assets.bushevski.com
VITE_STAGE=development|production
```

### Local Development

```bash
npm install
npm run dev
```

### Building for Production

```bash
npm run build
```

## Testing

Frontend includes:

- Unit tests for utility functions
- Component tests for key features
- Integration tests for booking flow
- E2E tests for critical paths

## Frontend Responsibilities

1. User Interface

   - Responsive design
   - Form validation
   - Date selection
   - Price calculation display
   - Loading states
   - Error handling

2. Data Management

   - Local state management
   - Form state
   - Booking flow progression
   - Temporary price calculations

3. Validation
   - Client-side form validation
   - Date range validation
   - Service option validation
   - File upload validation

## Backend Responsibilities

1. Data Persistence

   - Store bookings
   - Store customer information
   - Manage pricing rules
   - Store blocked dates

2. Business Logic

   - Validate bookings
   - Check availability
   - Calculate final prices
   - Process payments
   - Send confirmations

3. Security
   - Authentication
   - Authorization
   - Data validation
   - Rate limiting

## Important Notes

### Price Calculation

- Frontend calculates prices for display
- Backend must validate all prices
- Any discrepancy between frontend and backend calculations should fail the booking

### Date Handling

- All dates use ISO 8601 format
- Times are in 24-hour format
- All dates are in UTC
- Frontend handles local timezone conversion

### File Upload

- Driver's license files limited to 5MB
- Accepted formats: jpg, png, pdf
- Files stored in S3 with expiring URLs
- URLs valid for 1 hour

### Security Considerations

- No sensitive data in frontend state
- All API calls use HTTPS
- Admin routes require authentication
- Rate limiting on all endpoints

## Common Issues

1. Date Timezone Handling

   - Always use UTC for API calls
   - Convert to local time for display
   - Use date-fns for conversions

2. Price Calculation Discrepancies

   - Frontend calculations are estimates
   - Backend has final authority
   - Log discrepancies for monitoring

3. Form Validation
   - Frontend validates for UX
   - Backend validates for security
   - Sync validation rules between both

## Monitoring

Frontend monitors:

- JS errors
- API call success rates
- Page load times
- User interactions
- Booking funnel progression

## Future Considerations

1. Performance

   - Implement request caching
   - Optimize bundle size
   - Add service worker
   - Implement progressive loading

2. Features
   - Multiple language support
   - Payment integration
   - Review system
   - Booking modification
   - Cancellation handling
