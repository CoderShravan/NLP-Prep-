# NLP-Prep-
# My understanding :- 
So we need to collect every single piece of information about a customers via agents and store it in one place. To achieve this,rather than a dashboard that displays numbers and charts so rather than a human doing all analyses we make an agentic ai to do this
# Inital Issues
When you try to use a single, monolithic AI model to handle complex, enterprise-level tasks, it quickly runs into several major roadblocks. Think of it like asking one single employee to be the accountant, the customer service rep, the lawyer, and the software engineer all at the same time.It struggles to simultaneously analyze data, enforce strict business rules, and draft customer outreach without its reasoning becoming shallow or muddled.
Smart Solution : Using Multi Agentic Model-
Instead of one massive model doing it all, a Multi-Agent System divides the work into a team of specialized micro-models.In your Customer 360 scenario,for example, instead of one model trying to understand everything at once, you assign specialized roles.A Usage Agent looks only at app logins, a Support Agent looks only at angry tickets, and a Refiner Agent plays devil's advocate to double-check the final decision against company policy. This team-based approach allows the AI to work faster in parallel, catch each other's mistakes, and handle massive amounts of data without losing focus.
Architecture
