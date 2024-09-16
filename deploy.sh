#!/bin/bash

docker build -t tvilarim/pdf-db-creator:latest . &&
docker push tvilarim/pdf-db-creator:latest &&
docker pull tvilarim/pdf-db-creator:latest &&

kubectl apply -f k8s/redis-deployment.yaml &&
kubectl apply -f k8s/celery-worker-deployment.yaml &&
kubectl apply -f k8s/pdf-db-creator-deployment.yaml &&
kubectl apply -f k8s/pdf-db-creator-service.yaml &&
kubectl apply -f k8s/hpa.yaml
