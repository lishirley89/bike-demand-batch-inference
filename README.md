# Bike Demand Batch Inference

Streamlit app for visualizing bike share demand predictions from S3.

## Live App

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://bike-demand-batch-inference.streamlit.app/)

**Live Demo:** https://bike-demand-batch-inference.streamlit.app/

<iframe src="https://bike-demand-batch-inference.streamlit.app/?embed=true" height="600" width="100%" style="border:none;"></iframe>

## Features

- Interactive map visualization of bike share demand predictions
- Click on any location to see monthly predictions for that H3 cell
- Displays predictions for:
  - Classic Bike Start/End
  - E-Bike Start/End
- Automatically fetches the latest predictions from S3
- Cached data access for optimal performance


## Project Structure

```
.
├── app/
│   ├── streamlit_app.py    # Main Streamlit application
│   └── data_access.py      # S3 data access module with caching
├── artifacts/              # Local artifacts (gitignored)
├── .streamlit/
│   └── secrets.toml        # AWS credentials (gitignored)
├── requirements.txt        # Python dependencies
└── README.md
```


