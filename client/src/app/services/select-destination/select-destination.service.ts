// SPDX-FileCopyrightText: © 2023 Tobias Mühlberger
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Injectable } from '@angular/core';
import { ApiService } from 'src/app/api/services';
import { L10nService } from '../l10n/l10n.service';
import {
  BehaviorSubject,
  Observable,
  distinctUntilChanged,
  filter,
} from 'rxjs';
import {
  DestinationRead,
  DestinationSearchResult,
  SearchResultDestinationSearchResult,
} from 'src/app/api/models';

@Injectable({
  providedIn: 'root',
})
export class SelectDestinationService {
  private initializedSuggestedDestination = false;
  private selectedCountry?: string;
  private readonly selectedDestination = new BehaviorSubject<
    DestinationRead | undefined
  >(undefined);
  private readonly availableDestinations = new BehaviorSubject<
    DestinationSearchResult[] | undefined
  >(undefined);

  constructor(
    private readonly apiService: ApiService,
    private readonly l10nService: L10nService
  ) {
    l10nService
      .getCountry$()
      .pipe(
        distinctUntilChanged(),
        filter(c => c !== undefined && c !== null)
      )
      .subscribe({
        next: c => {
          this.selectedCountry = c;
          this.loadAvailableDestinations();
          if (!this.initializedSuggestedDestination) {
            this.renewSuggestedDestination();
            this.initializedSuggestedDestination = true;
          }
        },
      });
  }

  public getDestination$(): Observable<DestinationRead | undefined> {
    return this.selectedDestination.asObservable();
  }

  public getAvailableDestinations$(): Observable<
    DestinationSearchResult[] | undefined
  > {
    return this.availableDestinations.asObservable();
  }

  public renewSuggestedDestination(country?: string) {
    this.selectedDestination.next(undefined);
    this.apiService
      .getSuggestedDestination({ country: country || this.selectedCountry })
      .subscribe({
        next: d => this.selectedDestination.next(d),
      });
  }

  public selectDestination(destinationID: string) {
    this.selectedDestination.next(undefined);
    this.apiService.getDestinationById({ id: destinationID }).subscribe({
      next: d => {
        if (d.country !== this.selectedCountry && d.country) {
          this.l10nService.setCountry(d.country);
        }
        this.selectedDestination.next(d);
      },
    });
  }

  public searchDestination(
    quary: string
  ): Observable<SearchResultDestinationSearchResult> {
    return this.apiService.getDestinationsByName({
      name: quary,
      all_countries: true,
      country: this.selectedCountry,
    });
  }

  private loadAvailableDestinations() {
    if (!this.selectedCountry) {
      return;
    }
    this.apiService
      .getDestinationsByCountry({ country: this.selectedCountry })
      .subscribe({
        next: d => this.availableDestinations.next(d.results),
      });
  }
}
