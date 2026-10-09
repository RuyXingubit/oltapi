#!/bin/bash
while true; do
  STATUS=$(gh run view 37562205396 --json status -q '.status')
  if [ "$STATUS" = "completed" ]; then
    CONCLUSION=$(gh run view 37562205396 --json conclusion -q '.conclusion')
    if [ "$CONCLUSION" = "success" ]; then
      echo "Deploying..."
      sshpass -p 'oltisp12#' ssh -o StrictHostKeyChecking=no oltisp@olt.proserv.net.br "echo 'oltisp12#' | sudo -S sh -c 'cd /home/oltisp/oltapi && docker compose -f docker-compose.prod.yml pull oltapi frontend && docker compose -f docker-compose.prod.yml up -d oltapi frontend'"
    fi
    break
  fi
  sleep 5
done
