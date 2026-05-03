import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function LoadingCards() {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      {[...Array(6)].map((_, i) => (
        <Card key={i} className="h-full flex flex-col">
          <CardHeader className="space-y-3">
            <div className="flex items-center justify-between">
              <Skeleton className="h-12 w-12 rounded-lg" />
              <Skeleton className="h-6 w-24" />
            </div>
            <Skeleton className="h-7 w-3/4" />
          </CardHeader>
          <CardContent className="flex-1 space-y-4">
            <div className="space-y-2">
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-2/3" />
            </div>
            <Skeleton className="h-px w-full" />
            <Skeleton className="h-5 w-full" />
          </CardContent>
          <CardFooter>
            <Skeleton className="h-11 w-full rounded-lg" />
          </CardFooter>
        </Card>
      ))}
    </div>
  );
}
