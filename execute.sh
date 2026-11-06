TOKEN=$(.venv/bin/python scripts/mint_token.py)

.venv/bin/uvicorn app.api.main:app --reload

curl localhost:8000/diagnose \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"incident_id":"INC-204","equipment_id":"P-204","plant_id":"PLANT-A","symptoms":["vibracion alta"]}'
