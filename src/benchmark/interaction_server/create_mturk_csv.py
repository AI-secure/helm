import os
import json
import argparse
import csv
import uuid

scenario2Instructions = {
    "commonsense_dialogues": "When you start the chat, you will be given a scenario to discuss. For example, you may have the scenario “I lost my keys this morning. It was very stressful.” During the conversation, please talk as though you have experienced the scenario given. For this scenario, you might say something like “I had such a stressful morning! I couldn’t find my keys anywhere.” The goal of this task is to evaluate how well the chatbot understands common social scenarios.",
    "empatheticdialogues": "When you start the chat, you will be given a scenario to discuss. For example, you may have the scenario “I lost my keys this morning. It was very stressful.” During the conversation, please talk as though you have experienced the scenario given. For this scenario, you might say something like “I had such a stressful morning! I couldn’t find my keys anywhere.” The goal of this task is to evaluate how well the chatbot communicates empathetically.",
    "wizardofwikipedia": "When you start the chat, you will be given a topic to discuss. To the best of your ability, please talk with the chatbot about this topic. The goal of this conversation is to evaluate how well the chatbot discusses factual topics.",
}

scenario2GoalPrefix = {
    "commonsense_dialogues": "Discuss the following scenario as if it happened to you: ",
    "empatheticdialogues": "Discuss your emotions as if you were in this situation: ",
    "wizardofwikipedia": "Discuss the topic: ",
}
file_path = "benchmark_output/runs/"


def construct_url(task_name, trace_id, user_id, survey):
    base_url = "http://35.202.162.13:80/dialogue/interface?"
    # base_url = "http://localhost:8000/static/dialogue/interface.html?"
    base_url = base_url + "run_name=" + task_name  # Add parameters from task
    base_url = base_url + "&interaction_trace_id=" + trace_id  # Add trace_id
    base_url = base_url + "&user_id=" + str(user_id) 
    final_url = base_url + "&survey=" + survey # Add survey
    return final_url


def write_csv(in_fname, out_fname, survey):
    """
    In benchmark output
    Open scenario_state.json
    Iterate scenario_state.json
    write prompt + URL + instructions
    """
    # Get scenario-specific instructions
    idx = in_fname.index(":")
    scenario = in_fname[:idx]
    instructions = scenario2Instructions[scenario]

    # Iterate through json file
    full_path = os.path.join(file_path, in_fname, "scenario_state.json")
    out_dir = os.path.join(file_path, in_fname, "mturk_input")

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    out_path = os.path.join(out_dir, out_fname)

    # Set up csv
    out_file = open(out_path, "w")
    writer = csv.writer(out_file, delimiter=",")
    writer.writerow(["goal", "scenario_instructions", "url"])
    with open(full_path) as json_file:
        data = json.load(json_file)
        traces = data["interaction_traces"]
        for trace in traces:
            goal = scenario2GoalPrefix[scenario] + trace["instance"]["input"]
            trace_id = trace["_id"]
            user_id = uuid.uuid4()
            url = construct_url(in_fname, trace_id, user_id, survey)
            print(url) # Display in terminal for easy testing
            writer.writerow([goal, instructions, url])
    return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dir_name", type=str, help="Directory where scenario_state.json is located")
    parser.add_argument("-o", "--out_fname", type=str, default="mturk_out_file.csv", help="File to write output to")
    parser.add_argument("-s", "--survey", type=str, default="crfm-all", help="which survey to use")
    args = parser.parse_args()
    write_csv(args.dir_name, args.out_fname, args.survey)
    return


if __name__ == "__main__":
    main()
