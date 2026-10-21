"""Platform entry point. All modules deliberately live at the ZIP root."""
from agent_runner import THREADS, llm_plan, main, run_worker

if __name__ == '__main__':
    main()
