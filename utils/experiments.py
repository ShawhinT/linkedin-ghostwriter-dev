import os
import yaml
import csv
import json
import inspect
import random
from datetime import datetime
from utils.helpers import generate_post
from utils import evals

def discover_evals():
    """
    Automatically discovers all evaluation functions in utils.evals that start with 'eval_'.
    Returns a dictionary with eval configuration for each function.
    """
    eval_functions = {}
    
    # Get all functions from the evals module that start with 'eval_'
    for name, func in inspect.getmembers(evals, inspect.isfunction):
        if name.startswith('eval_'):
            # Get function signature
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            
            # Remove 'post' parameter as it's always the first argument
            args_params = [p for p in params if p != 'post']
            
            # Determine if LLM-based or code-based
            # Heuristic: if it has model_name, prompt_path, or other LLM-related params, it's LLM-based
            llm_indicators = {'model_name', 'prompt_path', 'model', 'prompt'}
            is_llm_based = any(param in llm_indicators for param in args_params)
            
            eval_type = "LLM-based" if is_llm_based else "code-based"
            
            # Get default values for parameters
            args_dict = {}
            if args_params:
                for param_name in args_params:
                    param = sig.parameters[param_name]
                    if param.default != inspect.Parameter.empty:
                        args_dict[param_name] = param.default
                    else:
                        args_dict[param_name] = None
            else:
                args_dict = None
            
            # Get function's docstring
            description = inspect.getdoc(func) or ""
            
            eval_functions[name] = {
                "description": description,
                "type": eval_type,
                "args": args_dict,
            }
    
    return eval_functions

# initialize experiment (create experiment folder with config.yaml, posts/, evals/, results.json    )
def init_experiment(prompt_path, input_path, model_name, notes="", temperature=1, num_posts=None):
    """
    Initializes an experiment by creating a folder with the given name.
    The folder contains:
        - config.yaml: configuration file
        - posts/: folder for posts
        - evals/: folder for evals
        - results.json: file for results
    
    Args:
        prompt_path: Path to the prompt file
        input_path: Path to the input CSV file
        model_name: Name of the model to use
        notes: Optional notes about the experiment
        temperature: Model temperature (default: 1)
        num_posts: Optional number of posts to generate. If None, uses all posts from input file.
    """
    # get current date in YYYY-MM-DD format
    current_date = datetime.now().strftime("%Y-%m-%d")

    # extract prompt_name from prompt_path (assuming format like "prompts/ghostwriter/prompt-v7.md")
    prompt_filename = prompt_path.split("/")[-1]  # e.g., "prompt-v7.md"
    prompt_name = prompt_filename.replace(".md", "")  # e.g., "prompt-v7"

    # extract input_name from input_path (assuming format like "data/inputs/inputs-10.csv")
    input_filename = input_path.split("/")[-1]  # e.g., "inputs-10.csv"
    input_name = input_filename.replace(".csv", "")  # e.g., "inputs-10"

    # count number of posts from input CSV file
    with open(input_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        # Skip header row
        next(reader, None)
        # Count remaining rows
        total_posts = sum(1 for row in reader)
        # Use num_posts if specified, otherwise use all posts
        num_posts = num_posts if num_posts is not None else total_posts

    # create experiment folder
    experiment_name = f"{current_date.replace("-", "_")}-{(prompt_name).replace("-", "_")}-{(input_name).replace("-", "_")}-num_posts_{num_posts}"
    experiment_folder = f"experiments/{experiment_name}"
    os.makedirs(experiment_folder, exist_ok=True)
    
    # create subdirectories
    os.makedirs(f"{experiment_folder}/posts", exist_ok=True)
    os.makedirs(f"{experiment_folder}/evals", exist_ok=True)

    # Automatically discover evaluation functions
    evals_config = discover_evals()

    # create config.yaml
    config = {
        "name": experiment_name,
        "date": current_date,
        "prompt_name": prompt_name,
        "prompt_path": prompt_path,
        "model": {
            "name": model_name,
            "temperature": temperature
        },
        "inputs": {
            "num_posts": num_posts,
            "total_posts": total_posts,
            "input_path": input_path
        },
        "evals": evals_config,
        "notes": notes
    }
    
    # write config to yaml file
    config_path = f"{experiment_folder}/config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # create empty results.json
    results_path = f"{experiment_folder}/results.json"
    with open(results_path, 'w') as f:
        f.write("{}")
    
    print(f"Experiment initialized: {experiment_folder}")
    # Print the entire YAML content
    print("\nConfig YAML content:")
    print(yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False))
    
    print("\n To make changes, edit the config.yaml file directly.")
    return experiment_folder

# generate posts
def generate_posts(experiment_folder):
    """
    Generates posts using the given prompt and model.
    """
    # load config
    with open(f"{experiment_folder}/config.yaml", "r") as file:
        config = yaml.safe_load(file)

    # load instructions
    with open(f"{config['prompt_path']}", "r") as file:
        instructions = file.read()
    
    # load model
    model_name = config["model"]["name"]
    temp = config["model"]["temperature"]
    
    # read inputs from inputs.csv and store in a list
    with open(config["inputs"]["input_path"], "r") as file:
        reader = csv.reader(file)
        next(reader) # skip header row
        user_input_list = [row[0] for row in reader]  # Extract first element from each row
    
    # Randomly select num_posts if specified
    num_posts = config["inputs"]["num_posts"]
    if num_posts < len(user_input_list):
        
        user_input_list = random.sample(user_input_list, num_posts)
    
    # generate posts
    for i, user_input in enumerate(user_input_list, 1):
        print(f"Generating post {i}/{len(user_input_list)}...")
        
        # generate post
        response = generate_post(instructions, user_input, model_name, temp)
        
        # create JSON structure
        post_data = {
            "input": user_input,
            "writing_steps": response.output_parsed.writing_steps,
            "final_post": response.output_parsed.final_post
        }
        
        # create filename with zero-padded numbering
        filename = f"post-{i:03d}.json"
        filepath = os.path.join(experiment_folder, "posts", filename)
        
        # write to JSON file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(post_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved: {filename}")
    
    print(f"All {len(user_input_list)} posts generated and saved to {experiment_folder}/posts/")

# function to run evals
def run_evals(experiment_folder):
    """
    Runs all evals for the given experiment.
    """
    # load config
    with open(f"{experiment_folder}/config.yaml", "r") as file:
        config = yaml.safe_load(file)

    # load evals
    evals_config = config['evals']

    # read posts from posts/ folder
    posts_folder = f"{experiment_folder}/posts"
    post_list = [f for f in os.listdir(posts_folder) if f.endswith('.json')]

    # run evals
    for eval_name, eval_info in evals_config.items():
        print(f"Running eval: {eval_name}")
        eval_func = getattr(evals, eval_name)
        
        # run eval for each post
        result_list = []
        for post in post_list:
            print(f"Running eval: {eval_name} for post: {post}")
            # load post 
            with open(f"{posts_folder}/{post}", "r") as file:
                post_data = json.load(file)
            # run eval
            result_list.append(eval_func(post_data['final_post']))

        # save results to evals/ folder
        csv_path = f"{experiment_folder}/evals/{eval_name}.csv"

        with open(csv_path, "w") as file:
            # Add post_id to the fieldnames
            fieldnames = ['post_id'] + list(result_list[0].keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            # Add post_id to each result row
            for post, result in zip(post_list, result_list):
                result_with_id = {'post_id': post.replace('.json', '')}
                result_with_id.update(result)
                writer.writerow(result_with_id)

        print(f"Results saved to {csv_path}")

# compute results of evals and save to results.json
def compute_results(experiment_folder):
    """
    Computes results of evals: num posts, pass/fail rate for each eval, average pass/fail rate,
    percent_all_passed, and percent_all_failed
    """
    # load config
    with open(f"{experiment_folder}/config.yaml", "r") as file:
        config = yaml.safe_load(file)
    
    # load eval results
    evals_folder = f"{experiment_folder}/evals"
    eval_result_list = [f for f in os.listdir(evals_folder) if f.endswith('.csv')]

    # Dictionary to store all results for each post: {post_id: [eval1_result, eval2_result, ...]}
    post_results = {}
    
    # compute results
    eval_name_list = []
    pass_rate_list = []
    for eval_result in eval_result_list:
        print(f"Computing results for {eval_result}")
        eval_name = eval_result.replace('.csv', '')
        eval_name_list.append(eval_name)
        
        # read eval results
        eval_path = f"{evals_folder}/{eval_result}"
        with open(eval_path, "r") as file:
            reader = csv.reader(file)
            next(reader) # skip header row
            eval_results = [row for row in reader]

        # compute results
        num_posts = len(eval_results)
        pass_rate = sum(1 for result in eval_results if result[1] == 'True') / num_posts
        pass_rate_list.append(pass_rate)
        
        # Store results for each post
        for result in eval_results:
            post_id = result[0]
            eval_passed = result[1] == 'True'
            if post_id not in post_results:
                post_results[post_id] = []
            post_results[post_id].append(eval_passed)

    # compute average pass/fail rate
    average_pass_rate = sum(pass_rate_list) / len(pass_rate_list)
    
    # compute percent_all_passed and percent_all_failed
    num_all_passed = 0
    num_all_failed = 0
    
    for post_id, results in post_results.items():
        if all(results):  # all evals passed
            num_all_passed += 1
        elif not any(results):  # all evals failed
            num_all_failed += 1
    
    percent_all_passed = num_all_passed / num_posts if num_posts > 0 else 0
    percent_all_failed = num_all_failed / num_posts if num_posts > 0 else 0

    # save results to results.json
    results = {
        "name": config["name"],
        "date": config["date"],
        "num_posts": num_posts,
        "average_pass_rate": average_pass_rate,
        "percent_all_passed": percent_all_passed,
        "percent_all_failed": percent_all_failed,
        "eval_results": {
            eval_name: {
                "pass_rate": pass_rate
            } for eval_name, pass_rate in zip(eval_name_list, pass_rate_list)
        }
    }
    with open(f"{experiment_folder}/results.json", "w") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    print(f"Results saved to {experiment_folder}/results.json")

def compute_summary():
    """
    Computes summary of results for all experiments and saves to summary.csv with the following columns:
    - experiment_name
    - model_name
    - temperature
    - num_posts
    - average_pass_rate
    - percent_all_passed
    - percent_all_failed    
    - eval_name-pass_rate (for each eval)
    """
    # get all experiment folders
    experiment_folders = [f for f in os.listdir("experiments") if os.path.isdir(f"experiments/{f}")]
    
    # compute summary
    summary = []
    for experiment_folder in experiment_folders:
        # load config
        with open(f"experiments/{experiment_folder}/config.yaml", "r") as file:
            config = yaml.safe_load(file)

        # load results
        with open(f"experiments/{experiment_folder}/results.json", "r") as file:
            results = json.load(file)

        # Create base summary entry
        summary_entry = {
            "experiment_name": results["name"],
            "model_name": config["model"]["name"],
            "temperature": config["model"]["temperature"],
            "num_posts": results["num_posts"],
            "average_pass_rate": results["average_pass_rate"],
            "percent_all_passed": results["percent_all_passed"],
            "percent_all_failed": results["percent_all_failed"]
        }

        # Add flattened eval results
        for eval_name, eval_data in results["eval_results"].items():
            summary_entry[f"{eval_name}-pass_rate"] = eval_data["pass_rate"]

        summary.append(summary_entry)

    # Sort by average_pass_rate in descending order (highest first)
    summary.sort(key=lambda x: x["average_pass_rate"], reverse=True)

    # save summary to summary.csv
    with open("experiments/summary.csv", "w") as file:
        writer = csv.DictWriter(file, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    print(f"Summary saved to summary.csv")