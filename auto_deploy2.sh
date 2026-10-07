#!/bin/bash
while true; do
  STATUS=$(gh run list --limit 1 | grep -E '^\*|^✓|^X|^-' | awk '{print $1}')
  echo "Current status: '$STATUS'"
  if [ "$STATUS" = "✓" ]; then
    echo "Build succeeded. Deploying..."
    sshpass -p 'oltisp12#' ssh -o StrictHostKeyChecking=no oltisp@olt.proserv.net.br "echo 'oltisp12#' | sudo -S sh -c 'cd /home/oltisp/oltapi && docker compose -f docker-compose.prod.yml pull oltapi frontend && docker compose -f docker-compose.prod.yml up -d oltapi frontend'"
    echo "Deploy complete!"
    break
  elif [ "$STATUS" = "X" ] || [ "$STATUS" = "-" ]; then
    echo "Build failed or cancelled. Aborting deploy."
    break
  fi
  sleep 15
done
