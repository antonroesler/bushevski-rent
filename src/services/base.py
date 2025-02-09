import os
from typing import Optional, Dict, Any
import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()


class BaseService:
    """Base service with DynamoDB client setup"""

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.table_name = os.environ["DYNAMODB_TABLE"]
        self.table = self.dynamodb.Table(self.table_name)

    def _create_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Create an item in DynamoDB"""
        try:
            self.table.put_item(Item=item)
            return item
        except ClientError as e:
            logger.error(f"Error creating item: {str(e)}")
            raise

    def _get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get an item from DynamoDB"""
        try:
            response = self.table.get_item(Key=key)
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Error getting item: {str(e)}")
            raise

    def _update_item(
        self,
        key: Dict[str, Any],
        update_expression: str,
        expression_values: Dict[str, Any],
        condition_expression: Optional[str] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Update an item in DynamoDB"""
        try:
            params = {
                "Key": key,
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_values,
                "ReturnValues": "ALL_NEW",
            }
            if condition_expression:
                params["ConditionExpression"] = condition_expression
            if expression_attribute_names:
                params["ExpressionAttributeNames"] = expression_attribute_names

            response = self.table.update_item(**params)
            return response.get("Attributes", {})
        except ClientError as e:
            logger.error(f"Error updating item: {str(e)}")
            raise

    def _query(
        self,
        key_condition_expression: str,
        expression_values: Dict[str, Any],
        index_name: Optional[str] = None,
        filter_expression: Optional[str] = None,
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> list:
        """Query items from DynamoDB"""
        try:
            params = {
                "KeyConditionExpression": key_condition_expression,
                "ExpressionAttributeValues": expression_values,
            }
            if index_name:
                params["IndexName"] = index_name
            if filter_expression:
                params["FilterExpression"] = filter_expression
            if expression_attribute_names:
                params["ExpressionAttributeNames"] = expression_attribute_names

            response = self.table.query(**params)
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Error querying items: {str(e)}")
            raise
