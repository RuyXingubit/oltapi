#!/bin/bash
while true; do
  STATUS=$(gh run list --limit 1 --json status -q '.[0].status')
  if [ "$STATUS" = "completed" ]; then
    CONCLUSION=$(gh run list --limit 1 --json conclusion -q '.[0].conclusion')
    if [ "$CONCLUSION" = "success" ]; then
      echo "Deploying..."
      sshpass -p 'oltisp12#' ssh -o StrictHostKeyChecking=no oltisp@olt.proserv.net.br "echo 'oltisp12#' | sudo -S sh -c 'cd /home/oltisp/oltapi && docker compose -f docker-compose.prod.yml pull oltapi frontend && docker compose -f docker-compose.prod.yml up -d oltapi frontend'"
    fi
    break
  fi
  sleep 10
done
