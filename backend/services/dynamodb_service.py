import boto3
from botocore.exceptions import ClientError
from typing import Optional
from datetime import datetime, timezone

from core.config import settings
from models.dynamodb import TaskRecord
from models.schemas import TaskStatus

# Initialize the DynamoDB resource using centralized settings
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
    region_name=settings.AWS_REGION
)

table = dynamodb.Table(settings.DYNAMODB_TABLE_NAME)

def create_task_record(record: TaskRecord) -> bool:
    """Inserts a new pending orchestration task into DynamoDB."""
    try:
        # model_dump(mode='json') handles Enum and Datetime serialization safely
        item = record.model_dump(mode='json')
        table.put_item(Item=item)
        return True
    except ClientError as e:
        print(f"[DB ERROR] Failed to create task {record.task_id}: {e.response['Error']['Message']}")
        return False

def get_task_record(task_id: str) -> Optional[TaskRecord]:
    """Retrieves a task by its ID."""
    try:
        response = table.get_item(Key={'task_id': task_id})
        item = response.get('Item')
        if item:
            return TaskRecord(**item)
        return None
    except ClientError as e:
        print(f"[DB ERROR] Failed to fetch task {task_id}: {e.response['Error']['Message']}")
        return None

def update_task_state(
    task_id: str, 
    status: TaskStatus, 
    vendor_results: list = None, 
    final_decision: dict = None,
    error_message: str = None
) -> bool:
    """
    Dynamically updates the state of a task using UpdateExpression.
    """
    update_expr = "SET #st = :status, updated_at = :updated_at"
    expr_attr_names = {"#st": "status"}
    
    expr_attr_values = {
        ":status": status.value,
        ":updated_at": datetime.now(timezone.utc).isoformat()
    }

    if vendor_results is not None:
        update_expr += ", vendor_results = :vr"
        expr_attr_values[":vr"] = vendor_results
        
    if final_decision is not None:
        update_expr += ", final_decision = :fd"
        expr_attr_values[":fd"] = final_decision
        
    if error_message is not None:
        update_expr += ", error_message = :err"
        expr_attr_values[":err"] = error_message

    try:
        table.update_item(
            Key={'task_id': task_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values
        )
        return True
    except ClientError as e:
        print(f"[DB ERROR] Failed to update task {task_id}: {e.response['Error']['Message']}")
        return False