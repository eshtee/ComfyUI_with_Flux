import argparse
import json
import random
import time
import requests
import uuid

class ComfyUIClient:
    def __init__(self, ip, port):
        self.url = f"http://{ip}:{port}"
        self.client_id = str(uuid.uuid4())

    def queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        prompt_url = f"{self.url}/prompt"
        try:
            r = requests.post(prompt_url, data=data)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as ex:
            print(f'POST {prompt_url} failed: {ex}')
            return None

    def get_queue(self):
        queue_url = f"{self.url}/queue"
        try:
            r = requests.get(queue_url)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as ex:
            print(f'GET {queue_url} failed: {ex}')
            return None

    def get_history(self, prompt_id):
        history_url = f"{self.url}/history/{prompt_id}"
        try:
            r = requests.get(history_url)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as ex:
            print(f'GET {history_url} failed: {ex}')
            return None

    @staticmethod
    def find_node_by_type(prompt, node_type):
        for node_id, node_info in prompt.items():
            if node_info.get("class_type") == node_type:
                return node_id
        return None

    @staticmethod
    def find_node_by_title(prompt, node_title):
        for node_id, node_info in prompt.items():
            if node_info.get("_meta", {}).get("title") == node_title:
                return node_id
        return None

    def run_workflow(self, filepath, prompt_override=None):
        with open(filepath, 'r') as file:
            prompt_text = json.load(file)

        prompt_node_id = self.find_node_by_title(prompt_text, "Positive Prompt")
        sampler_node_id = self.find_node_by_type(prompt_text, "KSampler")
        output_node_id = self.find_node_by_title(prompt_text, "Save Image")

        if not all([prompt_node_id, sampler_node_id, output_node_id]):
            print("Error: Could not find all required nodes in the workflow.")
            print(f"Positive Prompt Node: {'Found' if prompt_node_id else 'Not Found'}")
            print(f"KSampler Node: {'Found' if sampler_node_id else 'Not Found'}")
            print(f"Save Image Node: {'Found' if output_node_id else 'Not Found'}")
            return

        if prompt_override is not None:
            prompt_text[prompt_node_id]["inputs"]["text"] = prompt_override
        print(f'Prompt: {prompt_text[prompt_node_id]["inputs"]["text"]}')

        prompt_text[sampler_node_id]["inputs"]["noise_seed"] = random.randint(0, 1000000000000000)
        print(f'Seed: {prompt_text[sampler_node_id]["inputs"]["noise_seed"]}')

        response1 = self.queue_prompt(prompt_text)
        if response1 is None:
            print("Failed to queue the prompt.")
            return

        prompt_id = response1['prompt_id']
        print(f'Prompt ID: {prompt_id}')
        print('-' * 20)

        while True:
            time.sleep(5)
            queue_response = self.get_queue()
            if queue_response is None:
                continue

            queue_pending = queue_response.get('queue_pending', [])
            queue_running = queue_response.get('queue_running', [])

            for position, item in enumerate(queue_pending):
                if item[1] == prompt_id:
                    print(f'Queue running: {len(queue_running)}, Queue pending: {len(queue_pending)}, Workflow is in position {position + 1} in the queue.')

            for item in queue_running:
                if item[1] == prompt_id:
                    print(f'Queue running: {len(queue_running)}, Queue pending: {len(queue_pending)}, Workflow is currently running.')
                    break

            if not any(prompt_id in item for item in queue_pending + queue_running):
                break

        history_response = self.get_history(prompt_id)
        if history_response is None:
            print("Failed to retrieve history.")
            return

        output_info = history_response.get(prompt_id, {}).get('outputs', {}).get(output_node_id, {}).get('images', [{}])[0]
        filename = output_info.get('filename', 'unknown.png')
        output_url = f"{self.url}/output/{filename}"

        print(f"Output URL: {output_url}")


def main():
    parser = argparse.ArgumentParser(description='Add a prompt to the queue and wait for the output.')
    parser.add_argument('--ip', type=str, required=True, help='The public IP address of the pod (see "TCP Port Mappings" tab on Runpod.io)')
    parser.add_argument('--port', type=int, required=True, help='The external port of the pod (see "TCP Port Mappings" tab on Runpod.io)')
    parser.add_argument('--filepath', type=str, required=True, help='The path to the JSON file containing the workflow in api format')
    parser.add_argument('--prompt', type=str, required=False, help='The prompt to use for the workflow', default=None, nargs='*')
    args = parser.parse_args()

    client = ComfyUIClient(args.ip, args.port)
    prompt_override = ' '.join(args.prompt) if args.prompt is not None else None
    client.run_workflow(args.filepath, prompt_override)

if __name__ == "__main__":
    main()
