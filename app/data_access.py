#!/usr/bin/env python3
"""
Data access module for fetching predictions from S3.
"""

import json
import io
from typing import Optional, Dict, Any, List
import streamlit as st
import pandas as pd
import boto3
from botocore.exceptions import ClientError


# S3 configuration - loaded lazily to handle missing secrets gracefully
def get_s3_config():
    """Get S3 configuration from secrets with fallback defaults."""
    try:
        return {
            "bucket": st.secrets["S3_BUCKET"],
            "base_prefix": st.secrets["S3_BASE_PREFIX"],
            "model_version": st.secrets.get("MODEL_VERSION", "v0"),
            "region": st.secrets.get("AWS_DEFAULT_REGION", "us-east-1")
        }
    except (KeyError, AttributeError):
        # Fallback if secrets aren't configured (for testing/development)
        st.warning("S3 secrets not found. Using default configuration.")
        return {
            "bucket": "lishirley89",
            "base_prefix": "divvy-demand/predictions",
            "model_version": "v0",
            "region": "us-east-1"
        }

@st.cache_resource
def get_s3_client():
    """Get S3 client with configuration from secrets."""
    config = get_s3_config()
    return boto3.client("s3", region_name=config["region"])


@st.cache_data(ttl=300)  # Cache for 5 minutes
def list_run_dates(model_version: Optional[str] = None) -> List[str]:
    """
    List all available run_date prefixes for a given model version.
    
    Args:
        model_version: Model version (e.g., 'v0'). If None, uses default from config.
        
    Returns:
        List of run_date strings sorted by date (most recent first)
    """
    config = get_s3_config()
    if model_version is None:
        model_version = config["model_version"]
    s3_client = get_s3_client()
    prefix = f"{config['base_prefix']}/model={model_version}/"
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=config["bucket"], Prefix=prefix, Delimiter='/')
        
        run_dates = []
        for page in pages:
            # CommonPrefixes contains the "folders" (run_date=*)
            for prefix_info in page.get('CommonPrefixes', []):
                prefix_path = prefix_info['Prefix']
                # Extract run_date from prefix like "divvy-demand/predictions/model=v0/run_date=2025-12-25/"
                if 'run_date=' in prefix_path:
                    run_date = prefix_path.split('run_date=')[1].rstrip('/')
                    run_dates.append(run_date)
        
        # Sort by date descending (most recent first)
        run_dates.sort(reverse=True)
        return run_dates
    except ClientError as e:
        st.error(f"Error listing S3 prefixes: {e}")
        return []


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_latest_run_date(model_version: Optional[str] = None) -> Optional[str]:
    """
    Get the most recent run_date for a given model version.
    
    Args:
        model_version: Model version (e.g., 'v0')
        
    Returns:
        Most recent run_date string or None if not found
    """
    run_dates = list_run_dates(model_version)
    return run_dates[0] if run_dates else None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_manifest(
    model_version: Optional[str] = None,
    run_date: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch manifest.json from S3.
    
    Args:
        model_version: Model version (e.g., 'v0')
        run_date: Specific run_date to fetch. If None, uses the latest.
        
    Returns:
        Manifest dictionary or None if not found
    """
    config = get_s3_config()
    if model_version is None:
        model_version = config["model_version"]
    
    if run_date is None:
        run_date = get_latest_run_date(model_version)
        if run_date is None:
            st.error("No run_date found. Cannot fetch manifest.")
            return None
    
    s3_client = get_s3_client()
    manifest_key = f"{config['base_prefix']}/model={model_version}/run_date={run_date}/manifest.json"
    
    try:
        response = s3_client.get_object(Bucket=config["bucket"], Key=manifest_key)
        manifest_content = response['Body'].read().decode('utf-8')
        manifest = json.loads(manifest_content)
        return manifest
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'NoSuchKey':
            st.error(f"Manifest not found at s3://{config['bucket']}/{manifest_key}")
        else:
            st.error(f"Error fetching manifest: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Error parsing manifest JSON: {e}")
        return None


@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_csv_from_s3(
    model_version: Optional[str] = None,
    run_date: Optional[str] = None,
    csv_filename: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    Fetch and load CSV file from S3.
    
    Args:
        model_version: Model version (e.g., 'v0')
        run_date: Specific run_date to fetch. If None, uses the latest.
        csv_filename: Name of the CSV file. If None, fetches from manifest.
        
    Returns:
        DataFrame with the CSV data or None if not found
    """
    config = get_s3_config()
    if model_version is None:
        model_version = config["model_version"]
    
    # If csv_filename not provided, get it from manifest
    if csv_filename is None:
        manifest = fetch_manifest(model_version, run_date)
        if manifest is None:
            return None
        csv_filename = manifest.get('artifact')
        if csv_filename is None:
            st.error("No artifact specified in manifest.")
            return None
    
    # If run_date not provided, get the latest
    if run_date is None:
        run_date = get_latest_run_date(model_version)
        if run_date is None:
            st.error("No run_date found. Cannot fetch CSV.")
            return None
    
    s3_client = get_s3_client()
    csv_key = f"{config['base_prefix']}/model={model_version}/run_date={run_date}/{csv_filename}"
    
    try:
        response = s3_client.get_object(Bucket=config["bucket"], Key=csv_key)
        csv_content = response['Body'].read()
        
        # Stream the CSV into pandas
        df = pd.read_csv(io.BytesIO(csv_content))
        return df
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'NoSuchKey':
            st.error(f"CSV not found at s3://{config['bucket']}/{csv_key}")
        else:
            st.error(f"Error fetching CSV: {e}")
        return None
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        return None


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_predictions(
    model_version: Optional[str] = None,
    run_date: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    Convenience function to load predictions CSV from S3 using manifest.
    
    This function:
    1. Fetches the manifest (or uses latest if run_date not specified)
    2. Downloads the CSV file specified in the manifest
    3. Returns the DataFrame
    
    Args:
        model_version: Model version (e.g., 'v0')
        run_date: Specific run_date to fetch. If None, uses the latest.
        
    Returns:
        DataFrame with predictions or None if not found
    """
    return fetch_csv_from_s3(model_version, run_date, csv_filename=None)

