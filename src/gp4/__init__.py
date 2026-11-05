"""
gp4: AI-agent simulation of Hagtvedt and Brasel (2017), Study 3.

MBAN 5640 Visualization and Data Mining, Group Project 4, Group 1.

What this package does
----------------------
Simulates the "colour saturation increases perceived product size" experiment
with AI agents (one OpenAI vision-model call per simulated participant), then
compares the AI results with two human benchmarks: the original study (n = 77)
and the Motoki and Iseki (2022) replication (n = 823).

Pipeline (one module per job)
-----------------------------
1. config.py          Load and check all settings (config/config_v1.json).
2. benchmarks.py      Human results from the two papers, with sources.
3. agents.py          Build the roster of agents: condition and persona.
4. prompts.py         Assemble the exact text each agent receives.
5. llm_client.py      Call the model (or a mock for dry runs).        [Phase 3]
6. validate.py        Parse and check each answer; decide on retries.
7. run_experiment.py  Run all agents and save the data.               [Phase 3]
8. analysis.py        Statistics and the human-AI comparison.         [Phase 4]
9. plots.py           Figures for the dashboard and report.          [Phase 4]
"""

__version__ = "0.1.0"
