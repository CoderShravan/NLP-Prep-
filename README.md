# NLP-Prep-
# My understanding :- 
So we need to collect every single piece of information about a customers via agents and store it in one place.To achieve this,rather than a dashboard that displays numbers and charts and company just dumps data into it and a human doing all analyses we make an agentic ai to do this also there are pitfalls in using just one agent.
# Some Methods to Avoid
## Single AI Agent :-
So if we make a single agent to handle this,it will perform inefficiently like it wont be able to manage everything on its own that well.It struggles to simultaneously analyze data,sentiment analysis and draft a decision without its reasoning becoming shallow.
## Different States for each Agent :-
So even in multi agent if we make state seprately for each agent we
Smart Solution : Using Multi Agentic Model-
Instead of one massive model doing it all, a Multi-Agent System divides the work into a team of specialized micro-models.In your Customer 360 scenario,for example, instead of one model trying to understand everything at once, you assign specialized roles.A Usage Agent looks only at app logins, a Support Agent looks only at angry tickets, and a Refiner Agent plays devil's advocate to double-check the final decision against company policy. This team-based approach allows the AI to work faster in parallel, catch each other's mistakes, and handle massive amounts of data without losing focus.
Architecture
