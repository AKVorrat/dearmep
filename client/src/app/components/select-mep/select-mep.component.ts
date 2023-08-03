import { Component, OnInit, ViewChild } from '@angular/core';
import { FormControl } from '@angular/forms';
import { MatAutocompleteTrigger } from '@angular/material/autocomplete';
import { debounceTime, distinctUntilChanged, filter, map, Observable, shareReplay, startWith, switchMap, tap } from 'rxjs';
import { DestinationRead, DestinationSearchResult } from 'src/app/api/models';
import { CallingStep } from 'src/app/model/calling-step.enum';
import { CallingStateManagerService } from 'src/app/services/calling/calling-state-manager.service';
import { SelectDestinationService } from 'src/app/services/select-destination/select-destination.service';

@Component({
  selector: 'dmep-select-mep',
  templateUrl: './select-mep.component.html',
  styleUrls: ['./select-mep.component.scss']
})
export class SelectMEPComponent implements OnInit {
  public mepSelectionPossible$?: Observable<boolean>

  public selectedMEP$?: Observable<DestinationRead | undefined>
  public availableMEPs$?: Observable<DestinationSearchResult[] | undefined>
  public filteredMEPs?: Observable<DestinationSearchResult[] | undefined>

  public searchMEPFormControl = new FormControl<DestinationSearchResult | string | undefined>(undefined)

  public autocompleteIsLoading = false

  @ViewChild('destinationSearchInput', { read: MatAutocompleteTrigger })
  public autoComplete?: MatAutocompleteTrigger;

  constructor(
    private readonly callingStepManagerService: CallingStateManagerService,
    private readonly selectDestinationService: SelectDestinationService,
  ) { }

  public ngOnInit(): void {
    this.mepSelectionPossible$ = this.callingStepManagerService.getStep$().pipe(
      map(step => step !== CallingStep.Setup && step !== CallingStep.Feedback && step !== CallingStep.UpdateCallSchedule)
    )
    this.selectedMEP$ = this.selectDestinationService.getDestination$()
    this.availableMEPs$ = this.selectDestinationService.getAvailableDestinations$()

    const destinationsFromSameCountry$ = this.selectDestinationService.getAvailableDestinations$()

    this.filteredMEPs = this.searchMEPFormControl.valueChanges.pipe(
      tap((query) => {
        if (this.isSearchQuery(query)) {
          this.autocompleteIsLoading = true
        }
      }),
      debounceTime(100),
      startWith(undefined),
      distinctUntilChanged(),
      switchMap((query) => {
        if (!query || typeof query === 'object') {
          return destinationsFromSameCountry$;
        } else {
          return this.selectDestinationService.searchDestination(query).pipe(map(r => r.results))
        }
      }),
      tap(() => this.autocompleteIsLoading = false),
      shareReplay(),
    )

    // set selected mep from serach field
    this.searchMEPFormControl.valueChanges.pipe(
      filter(v => this.isSelectedDestination(v)),
      map(v => v as DestinationSearchResult)
    ).subscribe({
      next: (v) => this.selectDestinationService.selectDestination(v.id)
    })

    // Workaround to make sure autocomplete is opened
    // when search text changes
    this.searchMEPFormControl.valueChanges
      .pipe(filter(q => this.isSearchQuery(q)))
      .subscribe({
        next: () => {
          if (this.autoComplete && !this.autoComplete.panelOpen) {
            this.autoComplete.openPanel()
          }
        }
      })

    // reset search field if selected mep is not available in selected country
    destinationsFromSameCountry$.subscribe({
      next: (availableMEPs) => {
        const searchFieldValue = this.searchMEPFormControl.value
        if (searchFieldValue && typeof searchFieldValue === "object") {
          const found = !!availableMEPs?.find((m) => m.id === searchFieldValue?.id)
          if (!found) {
            this.searchMEPFormControl.reset()
          }
        }
      }
    })
  }

  public renewSuggestion() {
    this.searchMEPFormControl.reset()
    this.selectDestinationService.renewSuggestedDestination()
  }

  public getMepName(mep: DestinationSearchResult): string {
    return mep?.name || ''
  }

  // Value of search-field represents a string query to search for matching destinations
  private isSearchQuery(query: string | DestinationSearchResult | null | undefined): boolean {
    return !!query && typeof query === 'string' && query !== ''
  }

  // Value of search-field represents a selected destination object
  private isSelectedDestination(query: string | DestinationSearchResult | null | undefined): boolean {
    return !!query && typeof query === 'object'
  }
}