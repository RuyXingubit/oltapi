#!/bin/bash
while true; do
  STATUS=$(gh run list --limit 1 --json status,conclusion | jq -r '.[0].status')
  CONCLUSION=$(gh run list --limit 1 --json status,conclusion | jq -r '.[0].conclusion')
  echo "Status: $STATUS, Conclusion: $CONCLUSION"
  
  if [ "$STATUS" = "completed" ]; then
    if [ "$CONCLUSION" = "success" ]; then
      echo "Build succeeded. Deploying..."
      sshpass -p 'oltisp12#' ssh -o StrictHostKeyChecking=no oltisp@olt.proserv.net.br "echo 'oltisp12#' | sudo -S sh -c 'cd /home/oltisp/oltapi && docker compose -f docker-compose.prod.yml pull oltapi frontend && docker compose -f docker-compose.prod.yml up -d oltapi frontend'"
      echo "Deploy complete!"
      break
    else
      echo "Build failed or cancelled. Aborting deploy."
      break
    fi
  fi
  sleep 15
done
