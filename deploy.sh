#!/bin/bash

docker build -t tvilarim/pdf-db-creator:latest . &&
docker push tvilarim/pdf-db-creator:latest &&

kubectl apply -f k8s/deployment.yaml &&
kubectl apply -f k8s/service.yaml &&
kubectl apply -f k8s/hpa.yaml
