# Contributing to Websoft9

From opening a bug report to creating a pull request: every contribution is appreciated and welcome.   

If you're planning to implement a new feature or change the api please [create an issue](https://github.com/websoft9/websoft9/issues/new/choose) first. This way we can ensure that your precious work is not in vain.


##  Not Sure Architecture?

It's important to figure out the design [architecture of Websoft9](docs/architecture.md)

## Fork

Contributor only allow to fork [main branch](https://github.com/Websoft9/websoft9/tree/main) and pull request for it. Maintainers don't accept any pr to **production branch**

## Branch

This repository have these branchs:  

* **Contributor's branch**: Develpoer can fork main branch as their delelopment branch anytime 
* **main branch**: The only branch that accepts PR from Contributors's branch 
* **production branch**: For version release and don't permit modify directly, only merge PR from **main branch**


Flow: Contributor's branch → main branch → production branch


## Pull request

[Pull request](https://docs.github.com/pull-requests) let you tell others about changes you've pushed to a branch in a repository on GitHub.

#### When is PR produced?

* Contributor commit to main branch
* main branch commit to production branch

#### How to deal with PR?

1. [pull request reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews)
2. Merge RP and CI/CD for it

## DevOps principle

DevOps thinks the same way **[5m1e](https://www.dgmfmoldclamps.com/what-is-5m1e-in-injection-molding-industry/)** for manufacturing companies

We follow the development principle of minimization, rapid release

### Version

Use *[[major].[minor].[patch]](https://semver.org/lang/zh-CN/)* for version serial number and [version.json](../version.json) for version dependencies

### Artifact

Websoft9 use below [Artifact](https://jfrog.com/devops-tools/article/what-is-a-software-artifact/) for different usage:  

* **Dockerhub for image**: Access [Websoft9 docker images](https://hub.docker.com/u/websoft9dev) on Dockerhub
* **Azure Storage for files**: Access [packages list](https://artifact.azureedge.net/release?restype=container&comp=list) at [Azure Storage](https://learn.microsoft.com/en-us/azure/storage/storage-dotnet-how-to-use-blobs#list-the-blobs-in-a-container)

### Tags

- Type tags: Bug, enhancement, Documetation
- Stages Tags: PRD, Dev, QA(include deployment), Documentation

### WorkFlow

Websoft9 use the [Production branch with GitLab flow](https://cm-gitlab.stanford.edu/help/workflow/gitlab_flow.md#production-branch-with-gitlab-flow) for development collaboration

> [gitlab workflow](https://docs.gitlab.com/ee/topics/gitlab_flow.html) is improvement model for git
