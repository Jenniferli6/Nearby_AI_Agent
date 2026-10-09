"""Chat with the agent in a terminal:  python cli.py"""
import json
from nla.agent import LeadAgent

def main():
    agent = LeadAgent()
    print("Nearby lead agent (Durham, NC). Describe what's wrong at home. Ctrl-C to quit.\n")
    while True:
        try:
            msg = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg:
            continue
        print("\nnearby>", agent.reply(msg), "\n")
        if agent.lead.status == "submitted":
            print("=== LEAD SUBMITTED ===")
            print(json.dumps(agent.lead.model_dump(), indent=2))
            for d in agent.dispatch_payloads:
                print(f"\n--- to {d['provider_name']} {d['provider_phone']} ---\n{d['message']}")
            break

if __name__ == "__main__":
    main()
