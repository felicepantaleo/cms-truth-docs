// Writes every candidate of every trackster, with both association scores, as one JSON
// object per event. The adaptive argmin can then run outside CMSSW at any working point.

#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "DataFormats/HGCalReco/interface/Trackster.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/InputTag.h"
#include "PhysicsTools/TruthInfo/interface/Branch.h"
#include "SimDataFormats/Associations/interface/TICLAssociationMap.h"
#include "SimDataFormats/TruthInfo/interface/Graph.h"
#include "SimDataFormats/TruthInfo/interface/Particle.h"

namespace {
  using MapType = ticl::TICLAssociationMap<ticl::mapWithSharedEnergyAndScore>;

  struct Collection {
    std::string key;
    edm::EDGetTokenT<std::vector<ticl::Trackster>> tracksters;
    edm::EDGetTokenT<MapType> fixed;
    edm::EDGetTokenT<MapType> tight;
    edm::EDGetTokenT<MapType> nominal;
    edm::EDGetTokenT<MapType> truthToReco;
  };

  int64_t firstRoot(MapType const& map, std::size_t row) {
    auto const& rows = map.getMap();
    return row < rows.size() && !rows[row].empty() ? static_cast<int64_t>(rows[row][0].index()) : -1;
  }
}  // namespace

class TruthAdaptiveCandidateDumper : public edm::one::EDAnalyzer<> {
public:
  explicit TruthAdaptiveCandidateDumper(edm::ParameterSet const& cfg);
  ~TruthAdaptiveCandidateDumper() override;
  void analyze(edm::Event const& event, edm::EventSetup const&) override;

private:
  edm::EDGetTokenT<truth::Graph> graphToken_;
  edm::EDGetTokenT<std::vector<unsigned int>> assignableToken_;
  std::vector<Collection> collections_;
  std::FILE* out_ = nullptr;
};

TruthAdaptiveCandidateDumper::TruthAdaptiveCandidateDumper(edm::ParameterSet const& cfg)
    : graphToken_(consumes<truth::Graph>(cfg.getParameter<edm::InputTag>("graph"))),
      assignableToken_(consumes<std::vector<unsigned int>>(cfg.getParameter<edm::InputTag>("assignable"))),
      out_(std::fopen(cfg.getParameter<std::string>("output").c_str(), "w")) {
  const auto associator = cfg.getParameter<std::string>("associator");
  for (auto const& tag : cfg.getParameter<std::vector<edm::InputTag>>("recoCollections")) {
    std::string key = tag.label();
    if (!tag.instance().empty()) {
      key += "_" + tag.instance();
    }
    collections_.push_back({key,
                            consumes<std::vector<ticl::Trackster>>(tag),
                            consumes<MapType>(edm::InputTag(associator, key + "RecoToTruthFixed")),
                            consumes<MapType>(edm::InputTag(associator, key + "RecoToTruthAdaptiveTight")),
                            consumes<MapType>(edm::InputTag(associator, key + "RecoToTruthAdaptiveNominal")),
                            consumes<MapType>(edm::InputTag(associator, key + "TruthToReco"))});
  }
}

TruthAdaptiveCandidateDumper::~TruthAdaptiveCandidateDumper() {
  if (out_ != nullptr) {
    std::fclose(out_);
  }
}

void TruthAdaptiveCandidateDumper::analyze(edm::Event const& event, edm::EventSetup const&) {
  auto const& graph = event.get(graphToken_);
  auto const& assignable = event.get(assignableToken_);
  const auto generations = truth::particleGenerations(graph);
  const std::unordered_set<unsigned int> assignableIds(assignable.begin(), assignable.end());
  std::unordered_set<uint32_t> usedParticles;

  std::fprintf(out_, "{\"event\":%llu,\"collections\":{", static_cast<unsigned long long>(event.id().event()));
  bool firstCollection = true;
  for (auto const& col : collections_) {
    edm::Handle<std::vector<ticl::Trackster>> tracksters;
    event.getByToken(col.tracksters, tracksters);
    if (!tracksters.isValid()) {
      continue;
    }
    auto const& fixed = event.get(col.fixed);
    auto const& tight = event.get(col.tight);
    auto const& nominal = event.get(col.nominal);

    // (trackster, root) -> truth-normalised payload of the same pair.
    std::unordered_map<uint64_t, std::pair<float, float>> reversePayload;
    auto const& truthRows = event.get(col.truthToReco).getMap();
    for (std::size_t root = 0; root < truthRows.size(); ++root) {
      for (auto const& element : truthRows[root]) {
        reversePayload[(static_cast<uint64_t>(element.index()) << 32) | root] = {element.sharedEnergy(),
                                                                                  element.score()};
      }
    }

    std::fprintf(out_, "%s\"%s\":[", firstCollection ? "" : ",", col.key.c_str());
    firstCollection = false;
    auto const& rows = fixed.getMap();
    for (std::size_t t = 0; t < tracksters->size(); ++t) {
      auto const& trackster = (*tracksters)[t];
      std::fprintf(out_,
                   "%s[%.5g,%.5g,%.4f,%.4f,%lld,%lld,[",
                   t == 0 ? "" : ",",
                   trackster.raw_energy(),
                   trackster.raw_em_energy(),
                   trackster.barycenter().eta(),
                   trackster.barycenter().phi(),
                   static_cast<long long>(firstRoot(tight, t)),
                   static_cast<long long>(firstRoot(nominal, t)));
      if (t < rows.size()) {
        bool firstCandidate = true;
        for (auto const& element : rows[t]) {
          const uint32_t root = element.index();
          auto const payload = reversePayload.find((static_cast<uint64_t>(t) << 32) | root);
          if (payload == reversePayload.end()) {
            std::fprintf(stderr, "dumper: pair without a TruthToReco entry: trackster %zu root %u\n", t, root);
            continue;
          }
          usedParticles.insert(root);
          std::fprintf(out_,
                       "%s[%u,%.9g,%.9g,%.6g,%.6g,%d]",
                       firstCandidate ? "" : ",",
                       root,
                       element.score(),
                       payload->second.second,
                       element.sharedEnergy(),
                       payload->second.first,
                       assignableIds.contains(root) ? 1 : 0);
          firstCandidate = false;
        }
      }
      std::fprintf(out_, "]]");
    }
    std::fprintf(out_, "]");
  }

  std::fprintf(out_, "},\"particles\":{");
  bool firstParticle = true;
  for (const uint32_t id : usedParticles) {
    auto const& p = graph.particles()[id];
    int64_t parent = -1;
    uint32_t parentGeneration = 0;
    for (auto const& candidateParent : truth::Particle(&graph, id).parents()) {
      if (parent < 0 || generations[candidateParent.id()] > parentGeneration) {
        parent = candidateParent.id();
        parentGeneration = generations[candidateParent.id()];
      }
    }
    std::fprintf(out_,
                 "%s\"%u\":[%d,%.5g,%.5g,%.4f,%.4f,%u,%d,%u,%d,%d,%d,%lld]",
                 firstParticle ? "" : ",",
                 id,
                 p.pdgId,
                 p.momentum.E(),
                 p.momentum.pt(),
                 p.momentum.pt() > 0. ? p.momentum.eta() : 0.,
                 p.momentum.pt() > 0. ? p.momentum.phi() : 0.,
                 generations[id],
                 p.isFromPileup() ? 1 : 0,
                 p.levelFlags,
                 p.hasGen() ? 1 : 0,
                 p.hasSim() ? 1 : 0,
                 static_cast<int>(p.status),
                 static_cast<long long>(parent));
    firstParticle = false;
  }
  std::fprintf(out_, "}}\n");
  std::fflush(out_);
}

DEFINE_FWK_MODULE(TruthAdaptiveCandidateDumper);
