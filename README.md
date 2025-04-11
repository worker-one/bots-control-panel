# bots-control-panel


```
.
├── .env                  # Environment variables (DATABASE_URL)
├── app/                  # Main application package
│   ├── __init__.py
│   ├── crud.py           # Database interaction functions
│   ├── database.py       # Database connection setup
│   ├── main.py           # FastAPI app, routes
│   ├── models.py         # SQLAlchemy ORM models
│   ├── schemas.py        # Pydantic models (data shapes)
│   └── templates/
│       └── index.html    # HTML template for the UI
├── pyproject.toml        # Project definition and dependencies
└── README.md             # Instructions
```
