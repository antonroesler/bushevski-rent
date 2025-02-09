from datetime import date, timedelta
from typing import List, Dict
from aws_lambda_powertools import Logger

from services.base import BaseService
from models import BlockedDates, BlockedReason

logger = Logger()


class BlockedDatesService(BaseService):
    """Service for managing blocked dates"""

    def get_blocked_dates(self, start_date: date, end_date: date) -> List[BlockedDates]:
        """Get all blocked dates within a date range"""
        try:
            # Query all blocked periods that overlap with the date range
            items = self._query(
                key_condition_expression="GSI1PK = :pk AND GSI1SK BETWEEN :start AND :end",
                expression_values={
                    ":pk": "BLOCKED_DATES",
                    ":start": f"DATE#{start_date.isoformat()}",
                    ":end": f"DATE#{end_date.isoformat()}",
                },
                index_name="GSI1",
            )

            return [BlockedDates.from_dynamo(item) for item in items]

        except Exception as e:
            logger.error(f"Error getting blocked dates: {str(e)}")
            raise

    def get_blocked_dates_map(
        self, start_date: date, end_date: date
    ) -> Dict[str, BlockedReason]:
        """
        Get a map of all blocked dates within a range, with their reasons.
        Returns: Dict[date_str, reason]
        """
        try:
            blocked_periods = self.get_blocked_dates(start_date, end_date)

            # Create a map of date -> reason
            blocked_dates = {}

            # For each blocked period, add all dates within it
            for period in blocked_periods:
                current_date = period.start_date
                while current_date <= period.end_date:
                    blocked_dates[current_date.isoformat()] = period.reason
                    current_date += timedelta(days=1)

            return blocked_dates

        except Exception as e:
            logger.error(f"Error getting blocked dates map: {str(e)}")
            raise

    def create_blocked_period(self, blocked: BlockedDates) -> BlockedDates:
        """Create a new blocked period"""
        try:
            # Validate that dates don't overlap with existing blocked periods
            existing_blocks = self.get_blocked_dates(
                blocked.start_date, blocked.end_date
            )
            if existing_blocks:
                raise ValueError(
                    "New blocked period overlaps with existing blocked periods"
                )

            blocked_data = blocked.dict_for_dynamo()
            blocked_data["PK"] = f"BLOCKED_DATES#{blocked_data['id']}"
            blocked_data["SK"] = f"BLOCKED_DATES#{blocked_data['id']}"
            blocked_data["GSI1PK"] = "BLOCKED_DATES"
            blocked_data["GSI1SK"] = f"DATE#{blocked.start_date.isoformat()}"

            self._create_item(blocked_data)
            return blocked

        except Exception as e:
            logger.error(f"Error creating blocked period: {str(e)}")
            raise

    def delete_blocked_period(self, blocked_id: str) -> None:
        """Delete a blocked period"""
        try:
            self.table.delete_item(
                Key={
                    "PK": f"BLOCKED_DATES#{blocked_id}",
                    "SK": f"BLOCKED_DATES#{blocked_id}",
                }
            )
        except Exception as e:
            logger.error(f"Error deleting blocked period: {str(e)}")
            raise
