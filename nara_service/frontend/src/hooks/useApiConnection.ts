import { useState, useEffect } from "react";
import { checkHealth } from "@/lib/api";
import { ApiResponse } from "@/types";

export function useApiConnection() {
  const [apiData, setApiData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      const result = await checkHealth<ApiResponse>();
      if (result.success) {
        setApiData(result.data);
        setError(null);
      } else {
        setError("FastAPI 서버에 연결할 수 없습니다. http://localhost:8000 확인해주세요.");
        console.error("API Error:", result.error.message);
      }
      setLoading(false);
    };

    fetchData();
  }, []);

  return { apiData, loading, error };
}
