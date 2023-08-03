import {
  TRANSLOCO_LOADER,
  Translation,
  TranslocoLoader,
  TRANSLOCO_CONFIG,
  translocoConfig,
  TranslocoModule
} from '@ngneat/transloco';
import { Injectable, isDevMode, NgModule } from '@angular/core';
import { Observable, map } from 'rxjs';
import { ApiService } from './api/services';
import { ObjectUtil } from './common/util/object.util';


@Injectable({ providedIn: 'root' })
export class TranslocoHttpLoader implements TranslocoLoader {
  constructor(
    private apiService: ApiService,
  ) {}

  getTranslation(lang: string): Observable<Translation> {
    return this.apiService.getFrontendStrings({ language: lang })
    .pipe(
      map(r => ObjectUtil.UnflattenObject(r.frontend_strings) as Translation)
    )
  }
}

@NgModule({
  exports: [ TranslocoModule ],
  providers: [
    {
      provide: TRANSLOCO_CONFIG,
      useValue: translocoConfig({
        failedRetries: 3,
        reRenderOnLangChange: true,
        prodMode: !isDevMode(),
        missingHandler: {
          useFallbackTranslation: false
        }
      })
    },
    { provide: TRANSLOCO_LOADER, useClass: TranslocoHttpLoader }
  ]
})
export class TranslocoRootModule {}