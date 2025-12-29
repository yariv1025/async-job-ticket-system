"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import router
from .infra.dynamodb import DynamoDBRepositoryImpl
from .infra.sqs import SQSClientImpl
from .infra.parameter_store import ParameterStoreClientImpl
from .infra.metrics import CloudWatchMetricsClient
from .infra.logger import setup_logging, StructLogger
from .infra.xray import setup_xray, get_xray_middleware_class
from .service.job_service import JobService


# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(log_level)
logger = StructLogger("svc-api")

# Setup X-Ray
setup_xray("svc-api")


# Dependency injection container
class AppState:
    """Application state container."""

    def __init__(self):
        """Initialize application state."""
        self.job_service: JobService | None = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting svc-api...")

    # Get configuration from environment or Parameter Store
    env = os.getenv("ENV", "dev")
    region = os.getenv("AWS_REGION", "us-east-1")

    # Get table name and queue URL
    table_name = os.getenv("DDB_TABLE", "Jobs")
    queue_url = os.getenv("SQS_QUEUE_URL", "")
    
    # Initialize Parameter Store client (only if not in local dev)
    parameter_store = None
    if not os.getenv("AWS_ENDPOINT_URL"):
        # Only try Parameter Store in real AWS (not LocalStack)
        try:
            parameter_store = ParameterStoreClientImpl(region=region, env=env)
            table_name = os.getenv("DDB_TABLE", parameter_store.get_parameter("dynamodb/table-name"))
            queue_url = os.getenv("SQS_QUEUE_URL", parameter_store.get_parameter("sqs/queue-url"))
        except Exception as e:
            logger.warning(f"Failed to get parameters from Parameter Store, using env vars: {e}")
            table_name = os.getenv("DDB_TABLE", "Jobs")
            queue_url = os.getenv("SQS_QUEUE_URL", "")
    else:
        logger.info("Using LocalStack - using environment variables only")

    # Initialize infrastructure clients
    dynamodb_repo = DynamoDBRepositoryImpl(table_name=table_name, region=region)
    sqs_client = SQSClientImpl(region=region)
    metrics_client = CloudWatchMetricsClient(namespace="JobsSystem", region=region)

    # Create a parameter store wrapper that falls back to env vars for LocalStack
    if parameter_store is None:
        # For LocalStack, create a simple parameter store that uses env vars
        class EnvFallbackParameterStore:
            def __init__(self, queue_url_env: str):
                self._queue_url = queue_url_env
            
            def get_parameter(self, name: str) -> str:
                if name == "sqs/queue-url":
                    if not self._queue_url:
                        raise RuntimeError("SQS_QUEUE_URL environment variable not set")
                    return self._queue_url
                raise RuntimeError(f"Parameter {name} not available in local development")
        
        param_store_wrapper = EnvFallbackParameterStore(queue_url)
    else:
        param_store_wrapper = parameter_store

    # Initialize service
    app_state.job_service = JobService(
        dynamodb_repo=dynamodb_repo,
        sqs_client=sqs_client,
        parameter_store=param_store_wrapper,
        metrics_client=metrics_client,
        logger=logger,
    )

    logger.info("svc-api started successfully", table_name=table_name)

    yield

    # Shutdown
    logger.info("Shutting down svc-api...")


# Create FastAPI app
app = FastAPI(
    title="Job Ticket System API",
    description="API for submitting and querying async jobs",
    version="0.1.0",
    lifespan=lifespan,
)

# X-Ray is set up via boto3 patching (see setup_xray)
# No FastAPI middleware needed - X-Ray will trace AWS service calls automatically

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to inject job service
def get_job_service() -> JobService:
    """Get job service from app state."""
    if app_state.job_service is None:
        raise RuntimeError("Job service not initialized")
    return app_state.job_service


# Override route dependencies using middleware
@app.middleware("http")
async def inject_dependencies(request: Request, call_next):
    """Inject dependencies into request state."""
    if app_state.job_service:
        request.state.job_service = app_state.job_service
    response = await call_next(request)
    return response


# Include router
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "svc-api", "version": "0.1.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

