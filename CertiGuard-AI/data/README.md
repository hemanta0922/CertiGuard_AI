# Data directory

The dataset generator writes reproducible synthetic data to `data/generated/`. That generated folder is ignored by Git because every file can be rebuilt with:

```bash
python scripts/generate_certificate_dataset.py
```

Do not commit real certificates, student details, identity documents, issuer credentials, access tokens, or other personal/sensitive information. Only use synthetic or explicitly authorized and safely anonymized test data.
