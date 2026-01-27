from typing import List, Optional, Dict, Any

import requests


class FourCoreAttackService:
    """
    A Python class to interact with the FourCore ATTACK API.
    """

    def __init__(self, base_url: str, api_key: str):
        """
        Initializes the FourCoreAttackAPI client.

        Args:
            base_url (str): The base URL of the FourCore ATTACK API.
            api_key (str): The API key for authentication.
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None):
        """
        A helper function to make authenticated requests to the API.

        Args:
            method (str): The HTTP method (GET, POST, etc.).
            endpoint (str): The API endpoint.
            params (Optional[Dict[str, Any]]): URL parameters.
            json (Optional[Dict[str, Any]]): JSON body for POST/PUT requests.

        Returns:
            dict: The JSON response from the API.

        Raises:
            requests.exceptions.RequestException: For connection errors or HTTP error status codes.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, params=params, json=json)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err} - {response.text}")
            raise
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
            raise

    def get_assets(self) -> List[Dict[str, Any]]:
        """
        Retrieves all endpoint assets associated with the organization.
        Corresponds to GET /api/v2/assets.

        Returns:
            List[Dict[str, Any]]: A list of asset objects.
        """
        endpoint = "/api/v2/assets"
        return self._make_request('GET', endpoint)

    def get_chains_list(self, size: int = 10, offset: int = 0, filter_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Retrieves a list of attack chains.
        Corresponds to GET /api/v2/content/chains.

        Args:
            size (int): Maximum number of items to retrieve.
            offset (int): The starting index for retrieval.
            filter_params (Optional[Dict[str, Any]]): A dictionary of parameters to filter the results.
                Example: {'name': 'MyChain', 'platforms': 'windows'}

        Returns:
            Dict[str, Any]: A dictionary containing the list of chains and pagination details.
        """
        endpoint = "/api/v2/content/chains"
        params = {
            'size': size,
            'offset': offset
        }
        if filter_params:
            params.update(filter_params)

        return self._make_request('GET', endpoint, params=params)

    def get_chains_detail(self, chain_id: str) -> Dict[str, Any]:
        endpoint = f"/api/v1/content/chains/{chain_id}"
        return self._make_request('GET', endpoint)


    def get_executions(self, **kwargs) -> Dict[str, Any]:
        """
        Fetches all execution/simulation reports sorted by date.
        Corresponds to GET /api/v2/executions.

        Args:
            **kwargs: Arbitrary keyword arguments that are passed as query parameters.
                      Refer to the API documentation for available filters like 'size', 'offset',
                      'name', 'order', 'asset_id', 'status', etc.

        Returns:
            Dict[str, Any]: A dictionary containing the list of executions and pagination details.
        """
        endpoint = "/api/v2/executions"
        return self._make_request('GET', endpoint, params=kwargs)

    def get_execution_report(self, execution_id: str) -> Dict[str, Any]:
        """
        Gets an execution report with jobs and execution information.
        Corresponds to GET /api/v2/executions/{execution_id}/report.

        Args:
            execution_id (str): The ID of the execution.

        Returns:
            Dict[str, Any]: The detailed execution report.
        """
        endpoint = f"/api/v2/executions/{execution_id}/report"
        return self._make_request('GET', endpoint)

    def execute_endpoint_attack_chain(self, chain_id: str, **kwargs) -> Dict[str, Any]:
        """
        Executes an endpoint attack chain by its ID on specified assets.
        Corresponds to POST /api/v2/chains/{chain_id}/run.

        Args:
            chain_id (str): The ID of the chain to execute.
            **kwargs: The request body parameters.
                assets (List[str]): A list of asset IDs to run the attack on.
                disable_cleanup (bool): If true, cleanup will be disabled.
                run_elevated (bool): If true, the attack will run with elevated privileges.

        Returns:
            Dict[str, Any]: The response from the API, typically confirming the execution start.
        """
        endpoint = f"/api/v2/chains/{chain_id}/run"
        return self._make_request('POST', endpoint, json=kwargs)
