#!/bin/bash

confluent flink connection create openai-embedding --cloud gcp --region us-east1 --type openai --endpoint https://api.openai.com/v1/embeddings --api-key $OPENAI_API_KEY
