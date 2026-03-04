#!/usr/bin/env sh
set -e

BASE=http://localhost:8000

TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d '{"email":"researcher@example.com","password":"researcher123"}' | sed -E 's/.*"access_token":"([^"]+)".*/\1/')

echo "Token acquired"

PROJECT=$(curl -s -X POST $BASE/projects -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"title":"Smoke Project"}')
PID=$(echo "$PROJECT" | sed -E 's/.*"id":([0-9]+).*/\1/')

echo "Project $PID created"

curl -s -X POST $BASE/projects/$PID/advance-phase -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' > /dev/null
INVITE=$(curl -s -X POST $BASE/projects/$PID/invites -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}')
URL=$(echo "$INVITE" | sed -E 's/.*"invite_url":"([^"]+)".*/\1/' | sed 's#\\/##g')
TOKEN_INV=$(echo "$URL" | awk -F'/invite/' '{print $2}')

JOIN=$(curl -s -X POST $BASE/invite/$TOKEN_INV/join -H 'Content-Type: application/json' -d '{"name":"Alice","company":"ACME","consent":true}')
PART=$(echo "$JOIN" | sed -E 's/.*"participant_id":([0-9]+).*/\1/')

echo "Participant $PART joined"

curl -s -X PATCH $BASE/projects/$PID/phases/F2/entries -H 'Content-Type: application/json' -d "{\"actor_type\":\"participant\",\"actor_id\":$PART,\"field_key\":\"alignment_notes\",\"content\":\"Need better ML maintainability\"}" > /dev/null

curl -s -X POST $BASE/projects/$PID/advance-phase -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' > /dev/null
curl -s -X PATCH $BASE/projects/$PID/phases/F3/entries -H 'Content-Type: application/json' -d "{\"actor_type\":\"researcher\",\"actor_id\":1,\"field_key\":\"final_problem_statement\",\"content\":\"Formal statement\"}" > /dev/null

echo "Smoke flow executed"
