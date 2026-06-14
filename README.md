# Canadian Data Job Market Analysis

## Project Overview
This project provides a comprehensive evaluation of the Canadian data job market. By analyzing job postings, skill requirements, and salary trends, this analysis helps identify high-demand skill sets and their corresponding financial impact.

## Analysis Methodology
- **Data Source:** [lukebarousse/data_jobs](https://huggingface.co/datasets/lukebarousse/data_jobs)
- **Cleaning:** Standardized date formats and parsed JSON-like skill strings into actionable lists.
- **Filtering:** Focused on Canadian-based roles with a primary emphasis on Data Analyst positions.
- **Visualization:** Utilized `seaborn` and `matplotlib` to map market distribution, skill demand, and salary premiums.

## Visualizations

### 1. Market Distribution
*Overview of the top locations for data professionals across Canada.*

![Top 10 Locations](./images/top_10_locations.png)

### 2. Skill Demand
*Comparison of absolute demand vs. relative likelihood of skills in job postings.*

![Skill Counts](./images/skill_count_demand.png)

![Skill Likelihood](./images/skill_likelihood_demand.png)

### 3. Trending Skills
*Tracking the evolution of top-demand skills throughout the year.*

![Trending Skills](./images/trending_skills.png)

### 4. Compensation Analysis
*Salary distributions for top data roles and the premium paid for specific technical skills.*

![Salary Distribution](./images/salary_distribution.png)

![Highest Paid vs In-Demand](./images/skills_salary.png)

---

## Technical Stack
- **Language:** Python
- **Data Manipulation:** `pandas`, `ast`
- **Visualization:** `seaborn`, `matplotlib`
- **Dataset Access:** `datasets` (Hugging Face)

## How to Reproduce
1. **Clone the repository:**
```bash
   git clone https://github.com/joeguy57/data_analytics.git