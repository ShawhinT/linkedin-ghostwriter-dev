import streamlit as st
import pandas as pd
import json
import yaml
import os
from pathlib import Path

def load_experiment_folders():
    """Load all experiment folders from the experiments directory, sorted by name"""
    experiments_dir = Path("experiments")
    if not experiments_dir.exists():
        return []
    
    experiment_folders = [str(f) for f in experiments_dir.glob("*") if f.is_dir()]
    experiment_folders.sort(reverse=True)  # Sort newest first
    return experiment_folders

def load_experiment_data(experiment_folder):
    """Load experiment data including config, posts, and eval results"""
    folder_path = Path(experiment_folder)
    
    # Load config
    config_path = folder_path / "config.yaml"
    config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    
    # Load posts
    posts_dir = folder_path / "posts"
    posts = []
    if posts_dir.exists():
        for post_file in sorted(posts_dir.glob("post-*.json")):
            with open(post_file, 'r') as f:
                post_data = json.load(f)
                post_data['id'] = post_file.stem  # Add post ID
                posts.append(post_data)
    
    # Load eval results
    evals_dir = folder_path / "evals"
    eval_results = {}
    if evals_dir.exists():
        for eval_file in evals_dir.glob("eval_*.csv"):
            eval_name = eval_file.stem.replace('eval_', '')
            eval_results[eval_name] = pd.read_csv(eval_file)
    
    return config, posts, eval_results

def display_experiment_config(config):
    """Display experiment configuration in a user-friendly format"""
    st.markdown("### 📊 Experiment Configuration")
    
    # Create three columns for the config display
    general_col, inputs_col, evals_col = st.columns([1, 1, 1])
    
    with general_col:
        st.markdown("#### 🔧 General")
        
        # Display general configuration
        if 'name' in config:
            st.markdown(f"**Name:** {config['name']}")
        if 'date' in config:
            st.markdown(f"**Date:** {config['date']}")
        if 'prompt_name' in config:
            st.markdown(f"**Prompt:** {config['prompt_name']}")
        if 'prompt_path' in config:
            st.markdown(f"**Prompt Path:** `{config['prompt_path']}`")
        
        # Notes
        if 'notes' in config and config['notes']:
            st.markdown(f"**Notes:** {config['notes']}")
    
    with inputs_col:
        st.markdown("#### 📥 Inputs")

        # Other inputs
        if 'inputs' in config:
            inputs = config['inputs']
            for key, value in inputs.items():
                # Format key for display
                display_key = key.replace('_', ' ').title()
                
                # Special formatting for certain keys
                if 'path' in key.lower():
                    st.markdown(f"**{display_key}:** `{value}`")
                else:
                    st.markdown(f"**{display_key}:** {value}")
        elif 'model' not in config:
            st.markdown("*No input configuration found*")
        
        # Model information with its own subheader
        if 'model' in config:
            st.markdown("#### 🤖 Model")
            model = config['model']
            if 'name' in model:
                st.markdown(f"**Name:** {model['name']}")
            if 'temperature' in model:
                st.markdown(f"**Temperature:** {model['temperature']}")
            st.markdown("")  # Add spacing
    
    with evals_col:
        st.markdown("#### 📊 Evaluations")
        
        if 'evals' in config:
            evals = config['evals']
            for eval_name, eval_config in evals.items():
                # Format eval name for display
                display_name = eval_name.replace('_', ' ').title()
                st.markdown(f"**{display_name}:**")
                
                if 'description' in eval_config:
                    st.markdown(f"  - {eval_config['description']}")
                
                if 'type' in eval_config:
                    st.markdown(f"  - Type: {eval_config['type']}")
                
                # Put args in an expander
                if 'args' in eval_config and eval_config['args']:
                    with st.expander("Show Args"):
                        for arg_key, arg_value in eval_config['args'].items():
                            if 'path' in arg_key.lower():
                                st.markdown(f"**{arg_key}:** `{arg_value}`")
                            else:
                                st.markdown(f"**{arg_key}:** {arg_value}")
                
                st.markdown("")  # Add spacing between evals
        else:
            st.markdown("*No evaluation configuration found*")

def main():
    st.set_page_config(
        page_title="Experiment Results Viewer",
        page_icon="🔬",
        layout="wide"
    )
    
    st.title("🔬 Experiment Results Viewer")
    st.markdown("Review and analyze experiment results")
    
    # Experiment selection
    experiment_folders = load_experiment_folders()
    
    if not experiment_folders:
        st.error("No experiment folders found in the 'experiments' directory!")
        return
    
    selected_folder = st.selectbox(
        "Select an experiment:",
        experiment_folders,
        help="Choose the experiment folder to review"
    )
    
    if not selected_folder:
        return
    
    # Load experiment data
    config, posts, eval_results = load_experiment_data(selected_folder)
    
    if not posts:
        st.warning("No posts found in the selected experiment!")
        return
    
    # Display experiment metadata with improved formatting
    display_experiment_config(config)
    
    # Initialize session state for record navigation
    if 'post_index' not in st.session_state:
        st.session_state.post_index = 0
    
    # Ensure post_index is within bounds
    if st.session_state.post_index >= len(posts):
        st.session_state.post_index = len(posts) - 1
    elif st.session_state.post_index < 0:
        st.session_state.post_index = 0
    
    # Filter options
    st.markdown("### 🔍 Filter Options")
    filter_col1, filter_col2 = st.columns(2)
    
    # Create filter options for each eval type
    filters = {}
    for eval_name, eval_df in eval_results.items():
        with filter_col1 if len(filters) % 2 == 0 else filter_col2:
            filters[eval_name] = st.radio(
                f"Filter by {eval_name}:",
                ["All", "Passed", "Failed"],
                key=f"filter_{eval_name}"
            )
    
    # Apply filters
    filtered_posts = []
    for post in posts:
        include_post = True
        for eval_name, filter_value in filters.items():
            if filter_value != "All":
                eval_df = eval_results[eval_name]
                post_result = eval_df[eval_df['post_id'] == post['id']]['passed'].iloc[0]
                if (filter_value == "Passed" and not post_result) or \
                   (filter_value == "Failed" and post_result):
                    include_post = False
                    break
        if include_post:
            filtered_posts.append(post)
    
    if not filtered_posts:
        st.warning("No posts match the selected filters!")
        return
    
    st.markdown(f"### 📝 Posts ({len(filtered_posts)} matching filters)")
    
    # Post navigation
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Use session state for the selectbox
        new_index = st.selectbox(
            "Select Post:",
            range(len(filtered_posts)),
            index=min(st.session_state.post_index, len(filtered_posts) - 1),
            format_func=lambda x: f"Post {filtered_posts[x]['id']} of {len(filtered_posts)}",
            key="post_selectbox"
        )
        
        # Update session state if selectbox changed
        if new_index != st.session_state.post_index:
            st.session_state.post_index = new_index
    
    post_index = st.session_state.post_index
    
    # Navigation buttons
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([1, 1, 1, 1, 1])
    
    with nav_col1:
        if st.button("⏮️ First", disabled=(post_index == 0)):
            st.session_state.post_index = 0
            st.rerun()
    
    with nav_col2:
        if st.button("⏪ Previous", disabled=(post_index == 0)):
            st.session_state.post_index = max(0, post_index - 1)
            st.rerun()
    
    with nav_col3:
        st.metric("Progress", f"{post_index + 1}/{len(filtered_posts)}")
    
    with nav_col4:
        if st.button("Next ⏩", disabled=(post_index >= len(filtered_posts) - 1)):
            st.session_state.post_index = min(len(filtered_posts) - 1, post_index + 1)
            st.rerun()
    
    with nav_col5:
        if st.button("Last ⏭️", disabled=(post_index >= len(filtered_posts) - 1)):
            st.session_state.post_index = len(filtered_posts) - 1
            st.rerun()
    
    # Progress bar
    progress = (post_index + 1) / len(filtered_posts)
    st.progress(progress)
    
    # Display current post
    if post_index < len(filtered_posts):
        current_post = filtered_posts[post_index]
        
        # Create three columns for the main content
        left_col, middle_col, right_col = st.columns([1, 2, 1])
        
        with left_col:
            st.subheader("📄 User Input")
            user_input = current_post.get('input', '')
            st.text_area(
                "Input Content:",
                value=str(user_input),
                height=400,
                key=f"input_{post_index}",
                help="Read-only view of the user input"
            )
        
        with middle_col:
            st.subheader("🤖 Generated Post")
            final_post = current_post.get('final_post', '')
            st.text_area(
                "Final Post Content:",
                value=str(final_post),
                height=400,
                key=f"final_post_{post_index}",
                help="Read-only view of the final post"
            )
            
            # Add expander for Writing Steps
            writing_steps = current_post.get('writing_steps', '')
            if writing_steps:
                with st.expander("Show Writing Steps"):
                    st.text_area(
                        "Writing Steps:",
                        value=str(writing_steps),
                        height=300,
                        key=f"writing_steps_{post_index}",
                        help="Read-only view of the writing steps"
                    )
        
        with right_col:
            st.subheader("📊 Evaluation Results")
            
            # Display eval results for this post
            for eval_name, eval_df in eval_results.items():
                post_eval = eval_df[eval_df['post_id'] == current_post['id']]
                if not post_eval.empty:
                    passed = post_eval['passed'].iloc[0]
                    
                    # First row: eval name and pass/fail status
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.markdown(f"**{eval_name.replace('_', ' ').title()}**")
                    with cols[1]:
                        if passed:
                            st.success("✅ Pass")
                        else:
                            st.error("❌ Fail")
                    
                    # Second row: expander with all additional columns
                    with st.expander("Show Details"):
                        # Display all columns except 'post_id' and 'passed'
                        for col in post_eval.columns:
                            if col not in ['post_id', 'passed']:
                                st.markdown(f"**{col.title()}:**")
                                st.markdown(post_eval[col].iloc[0])

if __name__ == "__main__":
    main() 