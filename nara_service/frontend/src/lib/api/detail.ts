/**
 * Detail API - Get detail data
 */
import { BASE_URL, HEADERS, fetchWithTimeout } from './client';
import { DetailData } from '@/types';

export const getDetail = async (type: string, id: string): Promise<DetailData> => {
  const response = await fetchWithTimeout(`${BASE_URL}/detail/${type}/${id}`, {
    method: 'GET',
    headers: HEADERS,
  });

  return await response.json();
};
