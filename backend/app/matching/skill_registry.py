import re
from typing import Dict, Set, Optional, Tuple, List


# Canonical name map: lowercase alias -> canonical displayed name
SKILL_ALIASES: Dict[str, str] = {
    # Languages
    "python": "Python",
    "py": "Python",
    "python3": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "ruby": "Ruby",
    "php": "PHP",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "scala": "Scala",

    # Frameworks & Libraries
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "angular": "Angular",
    "angularjs": "Angular",
    "vue": "Vue",
    "vuejs": "Vue",
    "vue.js": "Vue",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "express": "Express",
    "expressjs": "Express",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "nestjs": "NestJS",
    "spring": "Spring Boot",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",

    # Cloud & DevOps
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "docker": "Docker",
    "terraform": "Terraform",
    "tf": "Terraform",
    "helm": "Helm",
    "ansible": "Ansible",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "github actions": "GitHub Actions",
    "gitlab ci": "GitLab CI",

    # Databases & Storage
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "kafka": "Kafka",
    "apache kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "elasticsearch": "Elasticsearch",

    # Architecture & Tools
    "graphql": "GraphQL",
    "rest": "REST API",
    "restful": "REST API",
    "rest api": "REST API",
    "microservices": "Microservices",
    "linux": "Linux",
    "git": "Git",
}

# Technologies that are strictly non-interchangeable
DISTINCT_TECHNOLOGY_GROUPS: List[Set[str]] = [
    {"React", "Angular", "Vue", "Svelte"},
    {"JavaScript", "TypeScript"},
    {"Java", "JavaScript"},
    {"Python", "Ruby"},
    {"Go", "Rust"},
    {"C++", "C#"},
]


class SkillRegistry:
    @staticmethod
    def normalize_skill(skill_str: str) -> str:
        """
        Normalizes a skill name by trimming, lowercasing, and looking up canonical aliases.
        """
        cleaned = skill_str.strip().lower()
        cleaned = re.sub(r"[\s_]+", " ", cleaned)

        # Direct alias lookup
        if cleaned in SKILL_ALIASES:
            return SKILL_ALIASES[cleaned]

        # Punctuation stripped lookup (e.g. "k8s," -> "Kubernetes")
        no_punct = re.sub(r"[^\w\s+#.]", "", cleaned)
        if no_punct in SKILL_ALIASES:
            return SKILL_ALIASES[no_punct]

        # Default title-cased representation
        return skill_str.strip().title()

    @classmethod
    def are_skills_equivalent(cls, skill_a: str, skill_b: str) -> bool:
        """Returns True if two skill strings resolve to the exact same canonical skill."""
        return cls.normalize_skill(skill_a) == cls.normalize_skill(skill_b)

    @classmethod
    def are_technologies_incompatible_substitutes(cls, skill_a: str, skill_b: str) -> bool:
        """
        Returns True if skill_a and skill_b belong to the same distinct group
        and therefore CANNOT be treated as equivalent substitutes.
        Example: React and Angular are distinct frontend frameworks; knowing React != knowing Angular.
        """
        norm_a = cls.normalize_skill(skill_a)
        norm_b = cls.normalize_skill(skill_b)
        if norm_a == norm_b:
            return False

        for group in DISTINCT_TECHNOLOGY_GROUPS:
            if norm_a in group and norm_b in group:
                return True
        return False

    @classmethod
    def extract_skills_from_text(cls, text: str) -> List[str]:
        """Extracts recognized canonical skills from unstructured job text."""
        found_skills = set()
        lower_text = " " + text.lower() + " "

        for alias, canonical in SKILL_ALIASES.items():
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(alias) + r"(?![a-zA-Z0-9])"
            if re.search(pattern, lower_text):
                found_skills.add(canonical)

        return sorted(list(found_skills))
