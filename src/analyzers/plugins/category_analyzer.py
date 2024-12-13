"""
This module contains the category analyzer plugin for the repository analyzer.
"""

from collections import deque
import json
from typing import Any, Dict, List
import asyncio
import time

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from tiktoken import Encoding


from analyzers.repository import PullRequestType
from config import settings, logger


class CategoryAnalyzerPlugin:
    """Base class for category analyzer plugins."""

    async def categorize(self, data: Any, feature_labels: List[str]) -> str:
        """Categorize the given data."""
        pass

    async def categorize_all(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[Dict]:
        """Categorize all the given data."""
        pass

    async def categorize_batch(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[Any]:
        """Categorize the given data."""
        pass


class PRTypeCategoryAnalyzerPlugin(CategoryAnalyzerPlugin):
    def categorize(self, data: Dict, feature_labels: List[str]) -> str:
        """
        Categorize pull request type based on metadata.

        Args:
            data (Dict): Pull request data

        Example:
            data = {
                "title": "Add new feature",
                "body": "This is a new feature",
                "labels": ["feature", "enhancement"]
            }

        Returns:
            PullRequestType: Classified pull request type based on content and labels.
        """
        title_lower = data.title.lower()
        combined_text = f"{title_lower} {data.body.lower() if data.body else ''}"
        labels_lower = [label.lower() for label in data.labels]

        result = None
        # Check labels first
        for label in labels_lower:
            if "feature" in label or "enhancement" in label:
                result = PullRequestType.FEATURE
            elif "bug" in label or "bugfix" in label:
                result = PullRequestType.BUGFIX
            elif "hotfix" in label or "critical" in label or "urgent" in label:
                result = PullRequestType.HOTFIX
            elif "test" in label or "testing" in label:
                result = PullRequestType.TEST
            elif "issue" in label:
                result = PullRequestType.ISSUE

        # Check title and body
        if any(
            keyword in combined_text for keyword in ["feature", "feat", "enhancement"]
        ):
            result = PullRequestType.FEATURE
        elif any(keyword in combined_text for keyword in ["fix", "bug", "issue #"]):
            result = PullRequestType.BUGFIX
        elif any(
            keyword in combined_text for keyword in ["hotfix", "critical", "urgent"]
        ):
            result = PullRequestType.HOTFIX
        elif any(keyword in combined_text for keyword in ["test", "testing"]):
            result = PullRequestType.TEST
        elif any(
            keyword in combined_text
            for keyword in ["refactor", "refactoring", "refact"]
        ):
            result = PullRequestType.REFACTOR
        elif "issue" in combined_text or "#" in title_lower:
            result = PullRequestType.ISSUE

        return result.value if result else PullRequestType.OTHER.value


class LLMPRTypeCategoryAnalyzerPlugin(CategoryAnalyzerPlugin):
    """
    LLM-based repository analyzer using OpenAI's GPT models.

    Analyzes repository data using LLM to classify PRs and generate metrics.
    Includes token counting and management.

    Attributes:
        intervals (List[int]): Time intervals for analysis in days
        client (AsyncOpenAI): OpenAI API client
        encoding (tiktoken.Encoding): Token encoder for the specified model
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        encoding: Encoding,
        max_requests: int,
        max_tokens: int,
        period: int,
        data_dir: str,
    ):
        """
        Initialize the LLM analyzer.

        Args:
            client (AsyncOpenAI): OpenAI API client
        """
        self.client = client
        self.encoding = encoding
        self.data_dir = data_dir
        self.request_times = deque()
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.period = period

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using the model's tokenizer.

        Args:
            text (str): Text to count tokens for

        Returns:
            int: Number of tokens in text
        """
        return len(self.encoding.encode(text))

    async def _rate_limit(self):
        """
        Rate limit the requests to the OpenAI API.
        This is to avoid rate limiting and ensure that we don't overload the API.
        """
        now = time.monotonic()
        # Remove timestamps older than the allowed period
        while self.request_times and (now - self.request_times[0]) > self.period:
            self.request_times.popleft()

        # If we're at capacity, wait until we're no longer rate-limited
        if len(self.request_times) >= self.max_requests:
            # Next available time slot is after the oldest request plus the period
            wait_time = self.period - (now - self.request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            # Clean up old timestamps again after waiting
            now = time.monotonic()
            while self.request_times and (now - self.request_times[0]) > self.period:
                self.request_times.popleft()

        # Record current request
        self.request_times.append(time.monotonic())

    def _prepare_pr_prompt(self, pr_data: Dict, feature_labels: List[str]) -> str:
        """
        Prepare prompt for PR classification.

        Args:
            pr_data (Dict): Pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            str: Formatted prompt for the LLM
        """
        return f"""Analyze this pull request and classify it into one of these categories: {', '.join(feature_labels)}.
        {{
            "pr_number": {pr_data["pr_number"]},
            "title": {pr_data["title"]},
            "body": {pr_data["body"] if pr_data["body"] else 'No description'},
            "labels": {', '.join(pr_data["labels"])}
        }}
        """

    def _prepare_batch_prompt(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> str:
        """
        Prepare a batch prompt for multiple PRs.

        Args:
            prs_data (List[Dict]): List of pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            str: Formatted batch prompt for the LLM
        """
        prs_text = "\n\n".join(
            f"Index: {pr['row']}\n"
            f"Number: {pr['number']}\n"
            f"Title: {pr['title']}\n"
            f"Description: {pr['body'] if pr['body'] else 'No description'}\n"
            f"Labels: {', '.join(pr['labels'])}"
            for i, pr in enumerate(prs_data)
        )

        return f"""Analyze each pull request and classify it into one of these categories: {', '.join(feature_labels)} and use lowercase.

{prs_text}

For each PR, respond with exactly one tuple (index, number, category) per line. Where index is the Index of the PR in the input list, number is the PR number, and category is the category of the PR.

Example:
(0, 123, "feature")
(1, 456, "bugfix")
(2, 789, "test")
"""

    async def categorize_all(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[Dict]:
        """This is a batch process and it will be rate limited.

        Args:
            prs_data (List[Dict]): List of pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            List[Dict]: List of classified PRs
        """

        async def rate_limited_categorize(pr_info, feature_labels):
            # Enforce rate limit before making request
            await self._rate_limit()
            return await self.categorize(pr_info, feature_labels)

        tasks = [rate_limited_categorize(data, feature_labels) for data in prs_data]
        pr_types = await asyncio.gather(*tasks)
        return pr_types

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def categorize(self, data: Dict, feature_labels: List[str]) -> Dict[str, str]:
        """
        Classify a single pull request using LLM.

        Args:
            data (Dict): Pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            Dict[str, str]: Classified PR type

        Raises:
            Exception: If classification fails
        """
        prompt = self._prepare_pr_prompt(data, feature_labels)
        token_count = self._count_tokens(prompt)
        logger.debug(f"Prompt token count: {token_count}")

        system_prompt = f"""You are a Staff Software Engineer at one of the top tech companies. 
        You will analyze a pull request and classify it into one of these categories: 
        {', '.join(feature_labels)}.
        You will be provided with input as:
        {{
            "pr_number": <number>,
            "title": <text>,
            "body": <text>,
            "labels": [<list of strings>]
        }}
        
        , and do your best to understand and infer a category other than "other". 
        Output a string containing the following information: "pr_number,category"
        - pr_number is the same as the input pr_number
        - category is your assigment category to the PR and must be one of the categories in the list
        """

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=10,
                timeout=120,
            )

            content = response.choices[0].message.content.strip().split(",")
            return {"pr_number": content[0], "pr_type": content[1]}
        except Exception as e:
            logger.error(f"Error classifying PR: {e}")
            raise e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def categorize_batch(
        self, prs_data: List[Dict], feature_labels: List[str]
    ) -> List[str]:
        """
        Classify multiple pull requests in batches.

        Args:
            prs_data (List[Dict]): List of pull request data
            feature_labels (List[str]): Available PR type labels

        Returns:
            List[str]: List of classifications in the same order as input PRs

        Raises:
            Exception: If batch processing fails
        """
        system_prompt = f"""You are a Staff Software Engineer at one of the top tech companies. 
        You will analyze multiple pull requests and classify each one into one of these categories: 
        {', '.join(feature_labels)}.
        You will be provided with input as:
        {{
            "pr_number": <number>,
            "title": <text>,
            "body": <text>,
            "labels": [<list of strings>]
        }}
        
        , and you will output a json object containing the following information:
        Example:
        {{
            "pr_number": <number>,
            "pr_type": <text>
        }}
        
        Respond with exactly one json object per line. Where pr_number is the PR number, and pr_type is the category of the PR.
        """

        logger.info(f"processing in a single batch {len(prs_data)} PRs")
        tasks = []
        for data in prs_data:
            task = {
                "custom_id": f"task-{data['row']}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    # This is what you would have in your Chat Completions API call
                    "model": "gpt-4o-mini",
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": {
                                "pr_number": data["pr_number"],
                                "title": data["title"],
                                "body": data["body"],
                                "labels": ", ".join(data["labels"]),
                            },
                        },
                    ],
                },
            }
            tasks.append(task)

        try:
            logger.info(f"creating the file with {len(tasks)} tasks")
            # 1. Creating the file
            file_name = f"{self.data_dir}/batch_tasks_classify_prs.jsonl"
            with open(file_name, "w") as file:
                for obj in tasks:
                    file.write(json.dumps(obj) + "\n")

            # 2. create batch file
            logger.info("creating the batch file")
            batch_file = await self.client.files.create(
                purpose="batch",
                file=open(file_name, "rb"),
            )

            # 3. create batch job
            logger.info("creating the batch job")
            batch_job = await self.client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
            )

            # 4. get batch job results
            logger.info("waiting for the batch job to complete")
            batch_job = await self.client.batches.retrieve(batch_job.id)
            # time how long it tool to complete
            start_time = time.time()
            while batch_job.status != "completed":
                time.sleep(60)
                batch_job = await self.client.batches.retrieve(batch_job.id)
            end_time = time.time()
            logger.info(
                f"batch job completed in {round((end_time - start_time) / 60, 2)} minutes"
            )

            # 5. get batch job results
            logger.info("batch job completed")
            result_file_id = batch_job.output_file_id
            result = await self.client.files.content(result_file_id).content

            result_file_name = f"{self.data_dir}/batch_tasks_classify_prs.jsonl"

            with open(result_file_name, "wb") as file:
                file.write(result)

            # cleanup - delete the files
            _ = await self.client.files.delete(result_file_id)
            _ = await self.client.files.delete(batch_file.id)

            # Loading data from saved file
            logger.info("loading the results from the file")
            results = []
            with open(result_file_name, "r") as file:
                for line in file:
                    # Parsing the JSON string into a dict and appending to the list of results
                    json_object = json.loads(line.strip())
                    result = json_object["response"]["body"]["choices"][0]["message"][
                        "content"
                    ]
                    results.append(
                        {
                            "pr_number": json_object["pr_number"],
                            "pr_type": result,
                        }
                    )

            logger.info("batch processing done ...")
            return results
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            raise e
