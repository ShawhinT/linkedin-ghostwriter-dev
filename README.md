# LinkedIn Ghostwriter (Dev)

Repository for LinkedIn ghostwriter development, including post generation, human annotation tools, LLM judge development, and experiment tracking.

Resources:
- [Video link]

## 🚀 Overview

This project provides a complete workflow for:
- **Generating LinkedIn posts** using AI models with carefully crafted prompts
- **Annotating and labeling** generated content for quality assessment
- **Evaluating posts** using both rule-based and LLM-based judges
- **Running experiments** to test different prompts, models, and configurations
- **Analyzing results** to improve post quality and voice consistency

## 📁 Project Structure

```
linkedin-writer/
├── .env                        # secret .env with OpenAI API key
├── 1-generate_posts.py          # Initial post generation script
├── 2-annotation_app.py          # Streamlit app for data annotation
├── 3-judge_dev_app.py          # Streamlit app for judge development
├── data/                       # Generated data and annotations
│   ├── inputs/                 # Input CSV files with post topics
│   └── [date-folders]/         # Timestamped data with annotations
├── experiments/                # Experiment results and configurations
│   ├── experiment_viewer.py    # Streamlit app for experiment visualization
│   └── summary.csv            # Aggregated experiment results
├── prompts/                   # Prompt templates
│   ├── ghostwriter/           # Content generation prompts
│   └── judge-voice/           # Voice evaluation prompts
├── utils/                     # Utility modules
│   ├── experiments.py         # Experiment management
│   ├── evals.py              # Evaluation functions
│   └── helpers.py            # Helper functions
```

## 🛠️ Core Components

### 1. Post Generation (`1-generate_posts.py`)
- Generates LinkedIn posts from unstructured user inputs
- Uses OpenAI's GPT models with structured output parsing
- Follows a systematic 7-step writing process
- Outputs structured data including writing steps and final posts

### 2. Annotation Tool (`2-annotation_app.py`)
- Streamlit-based web interface for manual post annotation
- Supports binary labeling and note-taking
- Tracks annotation progress and saves incrementally
- Handles multiple datasets and annotation sessions

### 3. Judge Development Tool (`3-judge_dev_app.py`)
- Interactive tool for developing and testing evaluation prompts
- Compare different judge versions and their performance
- Visualize metrics and confusion matrices
- Test judge consistency and reliability

### 4. Experimentation Framework (`utils/experiments.py`)
- Automated experiment setup and execution
- Configurable prompts, models, and evaluation criteria
- Systematic result tracking and comparison
- Batch processing for multiple configurations

## 🎯 Key Features

### Writing System
- **7-Step Writing Process**: Systematic approach to post creation
- **Voice Consistency**: Maintains Shaw's authentic voice and style
- **Structured Output**: Captures both process and final content
- **Prompt Versioning**: Multiple prompt iterations for optimization

### Evaluation System
- **Rule-Based Evaluators**: Automated checks (e.g., em-dash count)
- **LLM-Based Judges**: AI-powered voice and style evaluation
- **Multi-Criteria Assessment**: Comprehensive post quality metrics
- **Performance Tracking**: Historical evaluation results

### Data Management
- **Timestamped Data**: Organized by generation date
- **Annotation Tracking**: Persistent annotation state
- **Experiment Archival**: Complete experiment reproducibility
- **Result Aggregation**: Summary statistics across experiments