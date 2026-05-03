"use client";

import { useState, useEffect } from "react";
import { useApiConnection } from "@/hooks";
import { Header, QuerySection, Footer } from "@/components";
import { DetailModal } from "@/components/DetailModal";
import { DataCardComponent } from "./components/DataCard";
import { FilterButtonsComponent } from "./components/FilterButtons";
import { LoadingCards } from "./components/LoadingCards";
import { EmptyState } from "./components/EmptyState";
import { Pagination } from "./components/Pagination";
import { getIndex } from "@/lib/api";
import { ITEMS_PER_PAGE } from "./helpers";
import type { DataCard, FilterValue } from "./types";

// ==================== Main Component ====================
export default function Home() {
  const { apiData, loading, error } = useApiConnection();

  const [filterType, setFilterType] = useState<FilterValue>("ALL");
  const [searchText, setSearchText] = useState("");
  const [cards, setCards] = useState<DataCard[]>([]);
  const [cardsLoading, setCardsLoading] = useState(true);
  const [isDataListVisible, setIsDataListVisible] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedDetail, setSelectedDetail] = useState<{type: string, id: string} | null>(null);

  // Handler for opening detail modal
  const handleOpenDetail = (type: string, id: string) => {
    setSelectedDetail({type, id});
  };

  // Load index data
  useEffect(() => {
    const loadIndexData = async () => {
      setCardsLoading(true);
      try {
        const result = await getIndex();
        if (!result.success) {
          throw new Error(result.error.message);
        }
        const data = result.data;
        const cardList: DataCard[] = [];

        Object.keys(data).forEach((type) => {
          const typeData = data[type as keyof typeof data];

          Object.keys(typeData).forEach((id) => {
            const item = typeData[id];
            cardList.push({
              id: id,
              title: item.title,
              description: item.description,
              url: item.URL,
              type: type as DataCard["type"],
              update_time: item.update_time
            });
          });
        });

        cardList.sort((a, b) => b.update_time.localeCompare(a.update_time));

        setCards(cardList);
      } catch (err) {
        console.error("index 데이터 로드 실패:", err);
      } finally {
        setCardsLoading(false);
      }
    };

    loadIndexData();
  }, []);

  const filteredData = cards
    .filter(card => filterType === "ALL" || card.type === filterType)
    .filter(card =>
      searchText === "" ||
      card.title.toLowerCase().includes(searchText.toLowerCase())
    );

  // Calculate pagination
  const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = startIndex + ITEMS_PER_PAGE;
  const paginatedData = filteredData.slice(startIndex, endIndex);

  // Reset to page 1 when filter or search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [filterType, searchText]);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header loading={loading} error={error} apiData={apiData} />

      <main className="mx-auto flex-1 w-full flex flex-col">
        <div className="flex-1 flex flex-col w-full">
          {/* Main Search Area - Google Style */}
          <div className="w-full flex items-center justify-center px-4 sm:px-6 lg:px-8 py-24 transition-all duration-500 ease-in-out">
            <div className="w-full max-w-5xl mx-auto">
              <QuerySection 
                onToggleDataList={() => setIsDataListVisible(!isDataListVisible)}
                isDataListVisible={isDataListVisible}
              />
            </div>
          </div>

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
            {/* Data List Section - Conditionally Rendered */}
            {isDataListVisible && (
              <div className="space-y-8 animate-in fade-in slide-in-from-top-4 duration-300 pb-12">
                {/* Filter Buttons */}
                <FilterButtonsComponent
                  filterType={filterType}
                  setFilterType={setFilterType}
                  searchText={searchText}
                  setSearchText={setSearchText}
                  cards={cards}
                />

                {/* Data Cards */}
                {cardsLoading ? (
                  <LoadingCards />
                ) : filteredData.length === 0 ? (
                  <EmptyState />
                ) : (
                  <>
                    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 animate-in fade-in duration-500">
                      {paginatedData.map((card, index) => (
                        <div
                          key={card.id}
                          className="animate-in fade-in slide-in-from-bottom-4"
                          style={{ animationDelay: `${index * 50}ms`, animationFillMode: 'backwards' }}
                        >
                          <DataCardComponent card={card} onOpenDetail={handleOpenDetail} />
                        </div>
                      ))}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <Pagination
                        currentPage={currentPage}
                        totalPages={totalPages}
                        onPageChange={setCurrentPage}
                      />
                    )}

                    {/* Stats Footer */}
                    <div className="flex items-center justify-center pb-6">
                      <p className="text-base text-muted-foreground">
                        {startIndex + 1}-{Math.min(endIndex, filteredData.length)} / 총 <span className="font-semibold text-foreground">{filteredData.length}</span>개의 데이터
                        {filterType !== "ALL" && (
                          <span className="ml-1">
                            (전체: <span className="font-semibold text-foreground">{cards.length}</span>개)
                          </span>
                        )}
                      </p>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </main>

      <Footer />

      {/* Detail Modal */}
      <DetailModal
        type={selectedDetail?.type ?? null}
        id={selectedDetail?.id ?? null}
        open={!!selectedDetail}
        onClose={() => setSelectedDetail(null)}
      />
    </div>
  );
}
