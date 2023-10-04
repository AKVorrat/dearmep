import { Pipe, PipeTransform } from '@angular/core';
import { BaseUrlService } from '../services/base-url.service';

@Pipe({
  name: 'toAbsolute'
})
export class ToAbsolutePipe implements PipeTransform {
  constructor(
    private readonly baseUrlService: BaseUrlService,
  ) { }

  transform(url: string | undefined, type: "asset" | "api"): string | undefined {
    if (!url) {
      return url
    }
    if (type === "asset") {
      return this.baseUrlService.toAbsoluteAssetUrl(url)
    } else {
      return this.baseUrlService.toAbsoluteAPIUrl(url)
    }
  }
}
