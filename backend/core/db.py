import boto3
from botocore.exceptions import ClientError
from core.config import settings

def get_dynamodb_client():
    """
    Returns a DynamoDB client.
    Uses DYNAMODB_ENDPOINT_URL for local testing if provided.
    """
    client_kwargs = {
        "service_name": "dynamodb",
        "region_name": settings.AWS_REGION
    }
    
    if settings.DYNAMODB_ENDPOINT_URL:
        client_kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
        
    return boto3.client(**client_kwargs)

def get_dynamodb_resource():
    """
    Returns a DynamoDB resource object.
    Uses DYNAMODB_ENDPOINT_URL for local testing if provided.
    """
    resource_kwargs = {
        "service_name": "dynamodb",
        "region_name": settings.AWS_REGION
    }
    
    if settings.DYNAMODB_ENDPOINT_URL:
        resource_kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
        
    return boto3.resource(**resource_kwargs)

# For basic health check logic
def check_db_health() -> bool:
    try:
        client = get_dynamodb_client()
        client.list_tables(Limit=1)
        return True
    except ClientError:
        # DB unreachable or credentials issue
        return False
    except Exception:
        return False
