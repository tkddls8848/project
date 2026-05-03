import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ExternalLink, Calendar, Network } from "lucide-react";
import { getTypeIcon, getTypeDisplayName } from "../helpers";
import type { DataCard } from "../types";

interface DataCardProps {
  card: DataCard;
  onOpenDetail: (type: string, id: string) => void;
}

export function DataCardComponent({ card, onOpenDetail }: DataCardProps) {
  const TypeIcon = getTypeIcon(card.type);

  return (
    <Card className="group h-full flex flex-col hover:shadow-xl transition-all duration-300 hover:border-primary/50 overflow-hidden border border-gray-300 dark:border-neutral-800">
      <CardHeader className="space-y-2 pb-3 py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-muted p-1.5">
              <TypeIcon className="h-4 w-4 text-muted-foreground" />
            </div>
            <Badge className="text-xs font-medium px-2 py-0.5 bg-gray-100 text-gray-600 hover:bg-gray-100 dark:bg-gray-800/50 dark:text-gray-400">
              {getTypeDisplayName(card.type)}
            </Badge>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Calendar className="h-3 w-3" />
            <span className="font-mono">{card.update_time}</span>
          </div>
        </div>
        <CardTitle className="text-lg font-semibold line-clamp-2 group-hover:text-primary transition-colors leading-snug">
          {card.title}
        </CardTitle>
      </CardHeader>

      <CardContent className="flex-1 pb-3 space-y-3 py-0">
        <CardDescription className="text-sm leading-relaxed line-clamp-2">
          {card.description}
        </CardDescription>

        <Separator />

        <a
          href={card.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-2 group/link"
        >
          <ExternalLink className="h-3 w-3 shrink-0 group-hover/link:translate-x-0.5 transition-transform" />
          <span className="truncate font-mono">{card.url}</span>
        </a>
      </CardContent>

      <CardFooter className="pt-3 pb-3 border-t flex gap-2">
        <Button
          className="flex-1 group-hover:shadow-md transition-shadow h-9 text-sm rounded-lg"
          onClick={() => onOpenDetail(card.type, card.id)}
        >
          자세히 보기
          <ExternalLink className="ml-2 h-3 w-3" />
        </Button>
        <Button
          variant="outline"
          className="flex-1 group-hover:shadow-md transition-shadow h-9 text-sm rounded-lg"
          onClick={() => window.location.href = `/prometheus`}
        >
          <Network className="mr-2 h-3 w-3" />
          그래프로 보기
        </Button>
      </CardFooter>
    </Card>
  );
}
