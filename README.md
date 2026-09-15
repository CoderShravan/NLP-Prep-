# NLP-Prep-
# My understanding :- 
So we need to collect every single piece of information about a customers via agents and store it in one place.To achieve this,rather than a dashboard that displays numbers and charts and company just dumps data into it and a human doing all analyses we make an agentic ai to do this also there are pitfalls in using just one agent.
# Some Methods to Avoid
## Single AI Agent :-
So if we make a single agent to handle this,it will perform inefficiently like it wont be able to manage everything on its own that well.It struggles to simultaneously analyze data,sentiment analysis and draft a decision without its reasoning becoming shallow.
## Different States for each Agent :-
So even in multi agent if we make state separately for each agent as it wont provide full context and can lead to contradiction it might cause conflict leading to poor perfomance. So its really crucial that we make one shared state board for each customer so that each agents updates it and it gives better context overall of each state and then do analysis.`
## Vector Database as the Entire Memory :-
Storing every information as embeddings can lead to increased storage and retrieval costs,and loss of structured relationships between information.A better architecture separates current shared state,episodic memory,and summarized context,using vector retrieval only when semantic retrieval of past information is actually required. So its important to manage memory.

# Architeture
So we make a Multi-Agent System (MAS) where a complex task is divided among different specialized agents. An main agent first understands the task and assigns smaller tasks to the appropriate agents,such as a data analysis agent, sentiment analysis agent, research agent, and decision-making agent.
The architecture starts with customer data from the input stream such as support tickets, transactions, usage, KYC, and communication data flowing into a stream ingestion layer that handles both real-time events and scheduled triggers.These events activate a swarm of specialized agents such as Usage, Support/Sentiment, Transaction, and KYC agents, which independently analyze their respective signals and publish structured findings to a shared per-customer state board. A Synthesis layer then combines these findings with working, episodic, and semantic memory to understand the customer’s current situation. Based on this state,the system makes a bounded decision such as taking no action, offering retention support,HITL,guard-rail, giving an offer,etc. The proposed action then passes through eligibility/policy checks, critique/refinement, and deterministic guardrails, followed by a Human-in-the-Loop checkpoint for actions requiring approval. Once approved, the intervention is executed and its outcome is stored in episodic memory, while observability and audit logging track agent calls, tool usage, retrievals, handoffs, decisions, and human approvals throughout the system.  

#References -  
Large Language Model based Multi-Agents: A Survey of Progress and Challenges - https://arxiv.org/abs/2402.01680
ReAct: Synergizing Reasoning and Acting in Language Models - https://arxiv.org/abs/2210.03629
MemRetriever: Learning to Search, Reflect, and Retrieve from Long-Term Memory - https://arxiv.org/abs/2609.11951
Transforming business operations with multi-agent systems - https://aws.amazon.com/blogs/industries/transforming-business-operations-with-multi-agent-systems-field-workforce-safety-ai-assistant/
Got the graphical understanding from langchain docs the main idea is simple also got one aws blog related to it.
Also covered resources Tanishq Bhaiya has given
