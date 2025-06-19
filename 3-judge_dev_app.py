import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import glob
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
# Using numpy for metrics instead of scikit-learn
import json
from datetime import datetime
import time

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Pydantic model for LLM judge response
class JudgeResponse(BaseModel):
    """
    This is a Pydantic model for the LLM judge response.
    It is used to parse the response from the LLM.
    
    The response is a JSON object with the following fields:
        - reasoning_steps: all the reasoning steps taken to reach the final label (i.e. all text before the final label)
        - label: a boolean of the final label
    """
    reasoning_steps: str
    label: bool

# Numpy implementations of classification metrics
def accuracy_score_np(y_true, y_pred):
    """Calculate accuracy using numpy"""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    return np.mean(y_true == y_pred)

def confusion_matrix_np(y_true, y_pred, labels=None):
    """Calculate confusion matrix using numpy"""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    if labels is None:
        labels = np.unique(np.concatenate([y_true, y_pred]))
    
    n_labels = len(labels)
    label_to_index = {label: i for i, label in enumerate(labels)}
    
    cm = np.zeros((n_labels, n_labels), dtype=int)
    
    for true_label, pred_label in zip(y_true, y_pred):
        true_idx = label_to_index[true_label]
        pred_idx = label_to_index[pred_label]
        cm[true_idx, pred_idx] += 1
    
    return cm

def precision_recall_f1_np(y_true, y_pred, labels=None, average='weighted'):
    """Calculate precision, recall, and F1 score using numpy"""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    if labels is None:
        labels = np.unique(np.concatenate([y_true, y_pred]))
    
    # Calculate per-class metrics
    precisions = []
    recalls = []
    f1s = []
    supports = []
    
    for label in labels:
        # True positives, false positives, false negatives
        tp = np.sum((y_true == label) & (y_pred == label))
        fp = np.sum((y_true != label) & (y_pred == label))
        fn = np.sum((y_true == label) & (y_pred != label))
        
        # Support (number of true instances for this label)
        support = np.sum(y_true == label)
        supports.append(support)
        
        # Precision: tp / (tp + fp)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        precisions.append(precision)
        
        # Recall: tp / (tp + fn)
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        recalls.append(recall)
        
        # F1: 2 * (precision * recall) / (precision + recall)
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        f1s.append(f1)
    
    precisions = np.array(precisions)
    recalls = np.array(recalls)
    f1s = np.array(f1s)
    supports = np.array(supports)
    
    if average == 'weighted':
        # Weighted average by support
        total_support = np.sum(supports)
        if total_support == 0:
            return 0.0, 0.0, 0.0
        
        weights = supports / total_support
        precision_avg = np.sum(precisions * weights)
        recall_avg = np.sum(recalls * weights)
        f1_avg = np.sum(f1s * weights)
        
        return precision_avg, recall_avg, f1_avg
    elif average == 'macro':
        # Simple average
        return np.mean(precisions), np.mean(recalls), np.mean(f1s)
    else:
        # Return per-class metrics
        return precisions, recalls, f1s

# Streamlit page config
st.set_page_config(
    page_title="LLM Judge Development Tool",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚖️ LLM Judge Development Tool")
st.markdown("Compare prompt versions and evaluate performance on labeled datasets")

# Sidebar for configuration
st.sidebar.header("Configuration")

# Dataset selection
@st.cache_data
def load_available_datasets():
    """Load available dataset folders from data directory"""
    datasets = {}
    
    # Look for directories in data folder
    if os.path.exists("data"):
        for item in os.listdir("data"):
            item_path = os.path.join("data", item)
            if os.path.isdir(item_path):
                # Check if both required files exist
                posts_file = os.path.join(item_path, "request_response.csv")
                labels_file = os.path.join(item_path, "request_response-annotations.csv")
                
                if os.path.exists(posts_file) and os.path.exists(labels_file):
                    datasets[item] = {
                        'posts_file': posts_file,
                        'labels_file': labels_file,
                        'folder_path': item_path
                    }
    
    return datasets

datasets = load_available_datasets()

if len(datasets) == 0:
    st.sidebar.warning("No valid datasets found. Each folder in data/ should contain both 'request_response.csv' and 'request_response-annotations.csv'")
    selected_dataset = None
else:
    # Sort dataset names by folder name (newest first, assuming date is in name)
    sorted_datasets = sorted(datasets.keys(), reverse=True)
    selected_dataset = st.sidebar.selectbox("Select Dataset Folder", sorted_datasets)

# Load and preview dataset
@st.cache_data
def load_dataset(dataset_info):
    """Load dataset from posts and annotations files"""
    try:
        # Load posts file
        posts_df = pd.read_csv(dataset_info['posts_file'])
        
        # Load annotations file
        labels_df = pd.read_csv(dataset_info['labels_file'])
        
        # Combine datasets by index (same length and order)
        dataset_df = posts_df.copy()
        for col in labels_df.columns:
            if col not in posts_df.columns:
                dataset_df[col] = labels_df[col].values
        
        return dataset_df
    except Exception as e:
        st.error(f"Error loading dataset: {e}")
        return None

if selected_dataset:
    dataset_df = load_dataset(datasets[selected_dataset])
    
    if dataset_df is not None:
        st.sidebar.subheader("Dataset Preview")
        st.sidebar.write(f"Shape: {dataset_df.shape}")
        
        # Column mapping
        st.sidebar.subheader("Column Mapping")
        # Set default text column to "Final Post" if it exists, otherwise use first column
        default_text_col_index = 0
        if "Final Post" in dataset_df.columns:
            default_text_col_index = list(dataset_df.columns).index("Final Post")
        
        text_column = st.sidebar.selectbox("Text Column (LinkedIn Posts)", 
                                         dataset_df.columns, 
                                         index=default_text_col_index)
        label_column = st.sidebar.selectbox("Ground Truth Label Column", 
                                          [col for col in dataset_df.columns if col != text_column])

# Prompt selection
@st.cache_data
def load_available_prompts():
    """Load available prompts from prompts directory"""
    prompts = {}
    prompt_files = glob.glob("prompts/judge-voice/*.md")
    
    for file in prompt_files:
        name = os.path.basename(file).replace('.md', '')
        with open(file, 'r') as f:
            content = f.read()
        prompts[name] = {
            'path': file,
            'content': content
        }
    
    return prompts

prompts = load_available_prompts()

st.sidebar.subheader("Prompt Selection")
if len(prompts) == 0:
    st.sidebar.warning("No prompts found in prompts/judge-voice/")

selected_prompts = []
if len(prompts) > 0:
    prompt_names = list(prompts.keys())
    selected_prompts = st.sidebar.multiselect("Select Prompts to Compare", 
                                            prompt_names, 
                                            default=prompt_names[:2] if len(prompt_names) >= 2 else prompt_names)

# Evaluation settings
st.sidebar.subheader("Evaluation Settings")
sample_size = st.sidebar.slider("Sample Size for Evaluation", 5, 100, 30)
model_name = st.sidebar.selectbox("OpenAI Model", ["gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-04-14", "gpt-4o-2024-11-20", "gpt-4o-mini-2024-07-18", "o4-mini-2025-04-16"])

# Main content area
if selected_dataset and dataset_df is not None and len(selected_prompts) > 0:
    
    # Function to evaluate a single prompt
    def evaluate_prompt(prompt_content, texts, true_labels):
        """Evaluate a prompt on given texts and return predictions"""
        predictions = []
        reasoning_steps = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, text in enumerate(texts):
            try:
                status_text.text(f"Evaluating item {i+1}/{len(texts)}")
                
                # Updated to use responses API
                response = client.responses.parse(
                    model=model_name,
                    instructions=prompt_content,
                    input=text,
                    text_format=JudgeResponse,
                    temperature=0
                )
                
                # Extract parsed result and raw response
                predictions.append(response.model_dump()['output'][0]['content'][0]['parsed']['label'])
                reasoning_steps.append(response.model_dump()['output'][0]['content'][0]['parsed']['reasoning_steps'])
                
            except Exception as e:
                st.error(f"Error evaluating item {i+1}: {e}")
                predictions.append(-1)  # Changed from "error" to -1 for int consistency
                reasoning_steps.append(f"Error: {e}")
            
            progress_bar.progress((i + 1) / len(texts))
        
        progress_bar.empty()
        status_text.empty()
        
        return predictions, reasoning_steps
    
    # Function to calculate metrics
    def calculate_metrics(y_true, y_pred):
        """Calculate accuracy, precision, recall, and F1 score using numpy"""
        try:
            # Filter out error predictions (-1)
            valid_indices = [i for i, pred in enumerate(y_pred) if pred != -1]
            y_true_filtered = [y_true[i] for i in valid_indices]
            y_pred_filtered = [y_pred[i] for i in valid_indices]
            
            if len(y_true_filtered) == 0:
                return {"accuracy": 0, "precision": 0, "recall": 0, "f1": 0}
            
            # Convert to integers for binary classification
            y_true_int = [int(label) for label in y_true_filtered]
            y_pred_int = [int(label) for label in y_pred_filtered]
            
            # Calculate metrics using numpy implementations
            accuracy = accuracy_score_np(y_true_int, y_pred_int)
            precision, recall, f1 = precision_recall_f1_np(y_true_int, y_pred_int, average='weighted')
            
            return {
                "accuracy": round(accuracy, 3),
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
                "valid_predictions": len(y_true_filtered),
                "total_predictions": len(y_true)
            }
        except Exception as e:
            st.error(f"Error calculating metrics: {e}")
            return {"accuracy": 0, "precision": 0, "recall": 0, "f1": 0}
    
    # Sample data for evaluation
    sample_data = dataset_df.head(min(sample_size, len(dataset_df))).reset_index(drop=True)
    texts = sample_data[text_column].tolist()
    true_labels = sample_data[label_column].tolist()
    
    # Run evaluation button
    if st.button("🚀 Run Evaluation", type="primary"):
        
        results = {}
        
        for prompt_name in selected_prompts:
            st.subheader(f"Evaluating: {prompt_name}")
            prompt_content = prompts[prompt_name]['content']
            
            predictions, reasoning_steps = evaluate_prompt(prompt_content, texts, true_labels)
            metrics = calculate_metrics(true_labels, predictions)
            
            results[prompt_name] = {
                'predictions': predictions,
                'reasoning_steps': reasoning_steps,
                'metrics': metrics
            }
        
        # Store results in session state
        st.session_state['evaluation_results'] = results
        st.session_state['true_labels'] = true_labels
        st.session_state['texts'] = texts
        st.success("Evaluation completed!")

# Display results if available
if 'evaluation_results' in st.session_state:
    results = st.session_state['evaluation_results']
    true_labels = st.session_state['true_labels']
    texts = st.session_state['texts']
    
    # Summary table
    st.header("📊 Performance Summary")
    
    summary_data = []
    for prompt_name, result in results.items():
        metrics = result['metrics']
        summary_data.append({
            'Prompt': prompt_name,
            'Accuracy': metrics['accuracy'],
            'Precision': metrics['precision'],
            'Recall': metrics['recall'],
            'F1 Score': metrics['f1'],
            'Valid Predictions': f"{metrics.get('valid_predictions', 0)}/{metrics.get('total_predictions', 0)}"
        })
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True)
    
    # Confusion matrices
    st.header("🔍 Confusion Matrices")
    
    if len(selected_prompts) >= 2:
        col1, col2 = st.columns(2)
        columns = [col1, col2]
    else:
        columns = [st.container()]
    
    for i, (prompt_name, result) in enumerate(results.items()):
        with columns[i % len(columns)]:
            st.subheader(f"{prompt_name}")
            
            # Filter out error predictions for confusion matrix
            valid_indices = [j for j, pred in enumerate(result['predictions']) if pred != -1]
            y_true_filtered = [true_labels[j] for j in valid_indices]
            y_pred_filtered = [result['predictions'][j] for j in valid_indices]
            
            if len(y_true_filtered) > 0:
                # Convert all labels to strings to handle mixed types (bool/str)
                y_true_str = [str(label) for label in y_true_filtered]
                y_pred_str = [str(label) for label in y_pred_filtered]
                
                # Get unique labels
                labels = sorted(list(set(y_true_str + y_pred_str)))
                cm = confusion_matrix_np(y_true_str, y_pred_str, labels=labels)
                
                # Create heatmap
                fig = px.imshow(cm, 
                              x=labels, 
                              y=labels,
                              text_auto=True,
                              aspect="auto",
                              title=f"Confusion Matrix - {prompt_name}")
                fig.update_layout(
                    xaxis_title="Predicted",
                    yaxis_title="Actual",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No valid predictions to display confusion matrix")
    
    # Detailed results
    st.header("📋 Detailed Results")
    
    # Create detailed results dataframe with reordered columns
    detailed_data = []
    for i in range(len(texts)):
        row = {
            'Row': i + 1,
            'Text': texts[i][:100] + "..." if len(texts[i]) > 100 else texts[i],
            'True Label': true_labels[i]
        }
        
        # Add all predictions first (side by side)
        for prompt_name, result in results.items():
            row[f'{prompt_name} - Prediction'] = result['predictions'][i]
        
        # Then add all reasoning (truncated)
        for prompt_name, result in results.items():
            row[f'{prompt_name} - Reasoning'] = result['reasoning_steps'][i][:50] + "..." if len(result['reasoning_steps'][i]) > 50 else result['reasoning_steps'][i]
        
        detailed_data.append(row)
    
    detailed_df = pd.DataFrame(detailed_data)
    st.dataframe(detailed_df, use_container_width=True)
    
    # Preview section
    st.subheader("🔍 Preview Raw Responses")
    
    # Row selection for preview
    preview_row = st.number_input(
        "Enter row number to preview:",
        min_value=1,
        max_value=len(texts),
        value=1,
        step=1
    )
    
    if preview_row:
        row_idx = preview_row - 1
        
        # Show the full post text
        st.text_area(
            f"LinkedIn Post (Row {preview_row}):",
            texts[row_idx],
            height=300,
            key=f"post_text_{row_idx}"
        )

        
        # Show context for the selected row
        for prompt_name in selected_prompts:
            with st.expander(f"📄 {prompt_name} - Full Response"):
                raw_response = results[prompt_name]['reasoning_steps'][row_idx]
                prediction = results[prompt_name]['predictions'][row_idx]
                
                # Show prediction with color coding
                if prediction == true_labels[row_idx]:
                    st.success(f"Prediction: {prediction} ✅")
                else:
                    st.error(f"Prediction: {prediction} ❌")
                
                st.text_area(
                    f"Raw response from {prompt_name}:",
                    raw_response,
                    height=300,
                    key=f"raw_{prompt_name}_{row_idx}"
                )

    # Export results
    st.header("💾 Export Results")
    
    if st.button("Export Results to CSV"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/judge_evaluation_{timestamp}.csv"
        detailed_df.to_csv(filename, index=False)
        st.success(f"Results exported to {filename}")

else:
    st.info("👆 Configure your settings in the sidebar and click 'Run Evaluation' to get started!")
    
    # Show some helpful information
    st.header("ℹ️ How to Use")
    st.markdown("""
    1. **Select Dataset**: Choose a dataset containing LinkedIn posts and ground truth labels
    2. **Map Columns**: Specify which columns contain the text and labels
    3. **Choose Prompts**: Select one or more prompt versions to compare
    4. **Configure Settings**: Set sample size and model
    5. **Run Evaluation**: Click the button to start the evaluation process
    
    The tool will:
    - Generate predictions using each selected prompt
    - Calculate performance metrics (accuracy, precision, recall, F1)
    - Show confusion matrices for visual comparison
    - Provide detailed results for error analysis
    """)
    
    if len(prompts) == 0:
        st.warning("No prompts found. Create prompts in the `prompts/judge-voice/` directory as `.md` files.")
