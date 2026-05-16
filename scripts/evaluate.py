import json
import requests
from pathlib import Path

def recall_at_k(predicted: list, relevant: list, k: int = 10) -> float:
    top_k = set(predicted[:k])
    hits = sum(1 for name in relevant if name in top_k)
    return hits / len(relevant) if relevant else 0.0

def run_evaluation(traces_dir: str, api_url: str):
    scores = []
    trace_files = list(Path(traces_dir).glob('*.json'))
    
    if not trace_files:
        print(f"No trace files found in {traces_dir}")
        return

    print(f"Starting evaluation against {len(trace_files)} traces...")
    
    for trace_file in trace_files:
        trace = json.load(open(trace_file))
        print(f"\\nEvaluating trace: {trace_file.stem}")

        # Simulate multi-turn conversation
        messages = []
        final_recs = []
        
        for turn in trace['turns']:
            # 1. Add user message
            messages.append({'role': 'user', 'content': turn['user']})
            
            # 2. Call our API
            resp = requests.post(f'{api_url}/chat', json={'messages': messages})
            
            if resp.status_code != 200:
                print(f"  Error {resp.status_code}: {resp.text}")
                break
                
            data = resp.json()
            
            # 3. Add AI's reply to context
            messages.append({'role': 'assistant', 'content': data['reply']})

            # 4. Track latest recommendations
            if data.get('recommendations'):
                final_recs = [r['name'] for r in data['recommendations']]

            if data.get('end_of_conversation'):
                break

        # Calculate score for this trace
        score = recall_at_k(final_recs, trace['expected_assessments'])
        scores.append(score)
        print(f"  {trace_file.stem}: Recall@10 = {score:.3f}")
        print(f"  Expected: {trace['expected_assessments']}")
        print(f"  Agent Recommended: {final_recs}")

    print(f'\\nOverall Mean Recall@10: {sum(scores)/len(scores):.3f}')

if __name__ == '__main__':
    # Our local server needs to be running on port 8000
    run_evaluation('tests/fixtures/traces', 'http://localhost:8000')
