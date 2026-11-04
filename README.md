# Retinopathy ML Prototype

Academic, non-clinical prototype for retinal-image quality control, diabetic-retinopathy grading, uncertainty-aware abstention, and explanation aids.

## Local backend

```bash
cd backend
python -m pip install -e '.[test]'
uvicorn app.main:app --reload
```

The API processes one image at a time and does not retain image bytes, filenames, or patient identifiers. The current model services are deterministic CPU fallbacks intended for wiring and contract tests; training and evaluation belong in `ml/`.

The reviewed PostgreSQL migration is `sql/schema.sql`.
