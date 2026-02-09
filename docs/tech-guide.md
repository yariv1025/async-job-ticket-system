# Technology Guide

This document provides brief explanations of all the technologies and tools used in this project.

## AWS (Amazon Web Services)

AWS is Amazon's cloud computing platform that provides on-demand computing resources, storage, databases, and services over the internet. Instead of buying and maintaining physical servers, you rent cloud resources and pay only for what you use. AWS offers hundreds of services including compute, storage, databases, networking, analytics, machine learning, and more. It's the foundation for this entire project - all our infrastructure runs on AWS.

## DynamoDB

DynamoDB is AWS's fully managed NoSQL database service. It's a key-value and document database that delivers single-digit millisecond performance at any scale. Unlike traditional databases, you don't need to manage servers - AWS handles all the infrastructure. In this project, DynamoDB stores all job records with their status, parameters, and results. It automatically scales up or down based on traffic and provides built-in security, backup, and restore capabilities.

## SQS (Simple Queue Service)

SQS is AWS's fully managed message queuing service that enables you to decouple and scale microservices, distributed systems, and serverless applications. Think of it as a post office box - one service (API) puts messages in the queue, and another service (Worker) picks them up later. SQS ensures messages are delivered reliably, even if the worker is temporarily unavailable. In this project, the API publishes job messages to SQS, and the worker consumes them asynchronously.

## DLQ (Dead Letter Queue)

A Dead Letter Queue is a special SQS queue that holds messages that couldn't be processed successfully after multiple attempts. When a message fails processing repeatedly (exceeds maxReceiveCount), SQS automatically moves it to the DLQ. This prevents problematic messages from blocking the main queue and allows you to investigate failures separately. In this project, the DLQ triggers a Lambda function to mark jobs as permanently failed.

## Lambda

AWS Lambda is a serverless compute service that runs your code in response to events without requiring you to provision or manage servers. You just upload your code, and Lambda handles everything else - scaling, patching, monitoring. You pay only for the compute time you consume. In this project, a Lambda function processes messages from the DLQ and marks failed jobs in DynamoDB. It automatically scales to handle any number of messages.

## CloudWatch

CloudWatch is AWS's monitoring and observability service. It collects and tracks metrics, monitors log files, sets alarms, and automatically reacts to changes in your AWS resources. Think of it as a dashboard for your entire AWS infrastructure. In this project, CloudWatch stores logs from all services, tracks custom metrics (like job counts and processing times), and can trigger alarms if something goes wrong.

## X-Ray

AWS X-Ray is a service that helps you analyze and debug distributed applications. It provides a complete view of requests as they travel through your application, showing you which services are called, how long each call takes, and where errors occur. It's like a GPS tracker for your application flow. In this project, X-Ray traces requests from the API through SQS to the worker and Lambda, helping you understand performance bottlenecks and debug issues.

## Parameter Store (Systems Manager)

Parameter Store is part of AWS Systems Manager and provides secure, hierarchical storage for configuration data and secrets. Instead of hardcoding configuration values in your code, you store them in Parameter Store and retrieve them at runtime. It supports encryption, versioning, and fine-grained access control. In this project, Parameter Store holds configuration like DynamoDB table names, SQS queue URLs, and AWS region - making it easy to change settings without redeploying code.

## ECR (Elastic Container Registry)

ECR is AWS's fully managed Docker container registry that makes it easy to store, manage, and deploy Docker container images. Think of it as a private Docker Hub hosted on AWS. You build Docker images locally, push them to ECR, and then pull them when deploying to Kubernetes or other container services. In this project, ECR stores the Docker images for both the API and worker services before they're deployed to Kubernetes.

## Kubernetes (k8s)

Kubernetes (often abbreviated as k8s) is an open-source container orchestration platform that automates deploying, scaling, and managing containerized applications. It groups containers into logical units called "pods" and manages them across multiple servers. Kubernetes handles load balancing, self-healing (restarting failed containers), and scaling based on demand. In this project, Kubernetes runs both the API and worker services, ensuring they're always available and can scale as needed.

## Docker

Docker is a platform that packages applications and their dependencies into lightweight, portable containers. A container includes everything needed to run the application: code, runtime, system tools, libraries, and settings. Containers are isolated from each other and run consistently across different environments. In this project, Docker containers package the Python applications, making them easy to deploy anywhere - locally, on AWS, or in Kubernetes.

## FastAPI

FastAPI is a modern, fast web framework for building APIs with Python. It's designed for high performance and easy development, with automatic interactive API documentation. It uses Python type hints to validate request data and generate OpenAPI schemas automatically. In this project, FastAPI powers the API service, handling HTTP requests to create and query jobs. It provides automatic validation, serialization, and documentation.

## Python

Python is a high-level programming language known for its simplicity and readability. It's widely used for web development, data science, automation, and cloud applications. Python's extensive library ecosystem makes it ideal for AWS development. In this project, all services are written in Python 3.11, using libraries like boto3 for AWS interactions, FastAPI for the API, and structlog for logging.

## boto3

boto3 is the official AWS SDK (Software Development Kit) for Python. It provides Python APIs for AWS services, allowing you to interact with AWS resources programmatically from your Python code. Instead of using AWS CLI commands, you can write Python code to create DynamoDB tables, send SQS messages, or invoke Lambda functions. In this project, boto3 is used extensively to interact with DynamoDB, SQS, CloudWatch, Parameter Store, and other AWS services.

## LocalStack

LocalStack is a cloud service emulator that runs in a Docker container on your local machine. It provides a local testing environment for AWS services, allowing you to develop and test AWS applications without connecting to the real AWS cloud. It supports many AWS services including DynamoDB, SQS, Lambda, and more. In this project, LocalStack enables local development and testing without incurring AWS costs or requiring internet connectivity.

## IAM (Identity and Access Management)

IAM is AWS's service for managing access to AWS resources. It controls who (users, roles) can do what (permissions) on which resources. IAM follows the principle of least privilege - giving users and services only the minimum permissions they need. In this project, IAM policies define what each service can do: the API can write to DynamoDB and send SQS messages, the worker can read from SQS and update DynamoDB, and Lambda can only update DynamoDB.

## pytest

pytest is a popular Python testing framework that makes it easy to write and run tests. It provides simple syntax for writing test functions, powerful fixtures for test setup, and excellent reporting. It's widely used in the Python community for unit testing, integration testing, and more. In this project, pytest is used to test the API and worker services, ensuring code quality and correctness.

## moto

moto is a library that allows you to easily test code that uses boto3 by mocking AWS services. Instead of making real AWS API calls during tests (which would be slow and cost money), moto intercepts boto3 calls and returns mock responses. It supports many AWS services including DynamoDB, SQS, Lambda, and more. In this project, moto is used in tests to simulate AWS services locally without needing real AWS credentials or resources.

## structlog

structlog is a Python logging library that produces structured, machine-readable log output (typically JSON). Unlike traditional logging that produces plain text, structured logs include key-value pairs that make them easy to search, filter, and analyze. In this project, structlog is used throughout all services to produce JSON logs with correlation IDs (traceId, jobId) that can be easily analyzed in CloudWatch.

## Poetry

Poetry is a modern Python dependency management and packaging tool. It simplifies managing project dependencies, virtual environments, and building Python packages. Instead of using pip and requirements.txt, Poetry uses pyproject.toml to declare dependencies and handles version resolution automatically. In this project, Poetry manages dependencies for both the API and worker services, ensuring consistent environments across development and production.

## uvicorn

uvicorn is a lightning-fast ASGI (Asynchronous Server Gateway Interface) server implementation for Python web applications. It's designed to run async Python web frameworks like FastAPI, providing high performance and support for WebSockets. In this project, uvicorn runs the FastAPI application, handling HTTP requests and serving the API endpoints.

## SAM (Serverless Application Model)

SAM is an open-source framework for building serverless applications on AWS. It extends AWS CloudFormation with syntax for defining serverless resources like Lambda functions, API Gateways, and event source mappings. SAM templates are simpler than raw CloudFormation and include features like local testing and deployment. In this project, SAM is used to define and deploy the Lambda DLQ handler function.

## kubectl

kubectl is the command-line tool for interacting with Kubernetes clusters. It allows you to deploy applications, inspect cluster resources, view logs, and manage Kubernetes objects. Think of it as the "kubectl" (Kubernetes control) for your cluster. In this project, kubectl is used to deploy services to Kubernetes, check pod status, view logs, and manage the entire application deployment.

## JSON (JavaScript Object Notation)

JSON is a lightweight data-interchange format that's easy for humans to read and write, and easy for machines to parse and generate. It's the standard format for APIs and configuration files. In this project, JSON is used everywhere: API request/response bodies, DynamoDB item storage, SQS message bodies, log output, and configuration files.

## REST API

REST (Representational State Transfer) is an architectural style for designing web services. REST APIs use HTTP methods (GET, POST, PUT, DELETE) to perform operations on resources identified by URLs. They're stateless, meaning each request contains all information needed to process it. In this project, the API service exposes a REST API with endpoints like POST /jobs to create jobs and GET /jobs/{id} to retrieve job status.

## Idempotency

Idempotency is a property of operations where performing the same operation multiple times has the same effect as performing it once. For example, creating a job with the same idempotency key twice should result in only one job being created. In this project, idempotency is implemented using client-provided keys, ensuring that duplicate requests don't create duplicate jobs or process the same job multiple times.

## Exponential Backoff

Exponential backoff is a retry strategy where the wait time between retry attempts increases exponentially (e.g., 1 second, 2 seconds, 4 seconds, 8 seconds). This prevents overwhelming a failing service with rapid retry attempts and gives it time to recover. In this project, the worker uses exponential backoff when processing jobs fails due to transient errors, reducing unnecessary load while still attempting to complete the job.

## Correlation ID / Trace ID

A correlation ID (also called trace ID) is a unique identifier that's passed through all services involved in processing a single request. It allows you to trace a request's journey across multiple services by searching logs for the same ID. In this project, every job gets a traceId that's included in all log messages and passed through SQS messages, making it easy to debug issues by following a single job's lifecycle.

## Health Checks

Health checks are endpoints that report whether a service is running correctly. A liveness probe checks if the service is alive (not crashed), while a readiness probe checks if the service is ready to accept traffic (dependencies are available). In this project, /healthz reports liveness, and /readyz checks if DynamoDB is accessible, allowing Kubernetes to automatically restart unhealthy pods or route traffic only to ready instances.

